from datetime import datetime, timezone
import logging
import requests

from fastapi import APIRouter, Request, HTTPException, templating, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session

from db import crud, models
from dependencies.user import get_user_or_redirect
from dependencies.db import get_db
from schemas import schemas


NOAA_ORDER_URL = "https://q81rej0j12.execute-api.us-east-1.amazonaws.com/order"
NOAA_PICKUP_URL = "https://order-pickup.s3.amazonaws.com"
DEFAULT_GRID_RESOLUTION = 100  # 100m resolution default for now

templates = templating.Jinja2Templates(directory="templates")
noaa_router = APIRouter()


def bucket_to_url(bucket_location: str, base: str = NOAA_PICKUP_URL):
  """ Convert a bucket location to a public URL for download. """
  uuid = bucket_location.split("/")[-1]
  return f"{base}/{uuid}"

# TODO: Fix (actual enum or something nicer) - figure out what all the possible
# statuses are and make a prettier version of them
def prettier_status(status: str, url: str):
  if status == "complete":
    link = f"<a class='underline' href='{url}'>Download</a>" if url else ""
    return f"Complete! {link}"
  if status == "created":
    return "Created"
  if status == "initialized":
    return "Initialized"
  if status == "processing":
    return "Processing"
  logging.error(f"Didn't recognize this status: {status}")
  return "Order status unknown"


def bbox_to_flat(bbox: models.BoundingBox):
  # their convention is southwest corner to northeast corner, with lon first
  return (f"{bbox.top_left_lon},{bbox.bottom_right_lat},"
          f"{bbox.bottom_right_lon},{bbox.top_left_lat}")


def send_order_to_noaa(
    bbox: models.BoundingBox,
    data_type: str,
    user: models.User):
  """ Send an order to NOAA for data within the bounding box. """
  payload = {
    "bbox": bbox_to_flat(bbox),
    "email": user.email,
    "datasets": [
      {
        "label": data_type
      },
    ]
  }
  if data_type == "multibeam":
    payload["grid"] = {
      "resolution": DEFAULT_GRID_RESOLUTION # 100m resolution default for now
    }
  resp = requests.post(
    NOAA_ORDER_URL,
    headers={"Content-Type": "application/json"},
    json=payload
  )
  if not resp.ok:
    print(f"Error sending order to NOAA: {resp.status_code}")
    print(resp.json())
    raise Exception("Error sending order to NOAA")
  return resp.json()


@noaa_router.post("/order/{bbox_id}/{data_type}", include_in_schema=False)
def order(
    request: Request,
    bbox_id: int,
    data_type: str = "csb",
    db: Session = Depends(get_db),
    user: models.User = Depends(get_user_or_redirect)):
  
  if not request.headers.get("hx-request"):
    return RedirectResponse("/account")
  
  if data_type not in ["csb", "multibeam"]:
    raise HTTPException(
      status_code=404,
      detail="Data type not found"
    )

  if not (bbox := crud.get_bbox_by_id(db, bbox_id)):
    raise HTTPException(
      status_code=404,
      detail="Bounding box not found"
    )
 
  if bbox.owner_id != user.id:
    raise HTTPException(
      status_code=403,
      detail="You do not have permission to order data for this bbox"
    )

  try:  
    resp = send_order_to_noaa(bbox, data_type, user) 
  except Exception as e:
    logging.error(f"Error sending order to NOAA: {e}")
    raise HTTPException(
      status_code=500,
      detail="Error sending order to NOAA"
    )

  data_order = schemas.DataOrderCreate(
    noaa_ref_id=resp["url"].split("/")[-1],
    order_date=datetime.now(timezone.utc).isoformat(),
    check_status_url=resp["url"],
    bbox_id=bbox_id,
    user_id=user.id,
    data_type=data_type
  )
  crud.create_data_order(db, user.id, data_order)

  return templates.TemplateResponse(
    "partials/order_table.html", {
      "request": request,
      "current_user": user,
      "status_url": resp["url"],
      "message": resp["message"],
    })


@noaa_router.get("/order_status/{order_id}", include_in_schema=False)
def order_status(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db),
    user: schemas.User = Depends(get_user_or_redirect)) -> str:
  
  if not request.headers.get("hx-request"):
    return RedirectResponse("/account")
  
  
  if not (order := crud.get_data_order_by_id(db, order_id)):
    raise HTTPException(
      status_code=404,
      detail="Order not found"
    )
  
  if order.user_id != user.id:
    raise HTTPException(
      status_code=403,
      detail="You do not have permission to view this order"
    )
  
  if "complete" not in order.last_status.lower():
    # this is just to be nice and not hammer the NOAA api if we know the order
    # is complete
    try:
      res = requests.get(order.check_status_url).json()
      loc = res.get("output_location", None)
      order.output_location = bucket_to_url(loc) if loc else None
      order.last_status = prettier_status(res["status"], order.output_location)
    except Exception as e:
      logging.error(f"Error getting order status: {e}")
      order.last_status = prettier_status("unknown", None)
    db.commit()

  # assuming we want to stop by default - so far I have only seen complete and
  # and initialized statuses, created is mine
  # so this only keeps going in the cases where I've seen that it should so far
  http_status = 286 # 286 is a custom htmx status code to stop polling
  if "complete" not in order.last_status.lower():
    http_status = 200  # tells htmx to continue polling
  
  return HTMLResponse(
    order.last_status,
    status_code=http_status
  )


# An incoming post handler to receive SNS notifications from NOAA
@noaa_router.post("/sns", include_in_schema=False)
async def sns(request: Request):
  try:
    # Needs to acknowledge the subscription / confirm it (only the first time)
    data = await request.json()
    print(data)
    if data["Type"] == "SubscriptionConfirmation":
      resp = requests.get(data["SubscribeURL"])
      if not resp.ok:
        raise Exception("Error confirming subscription")
      message = data["Message"]
      print(message)
    if data["Type"] == "Notification":
      message = data["Message"]
      print(message)
  except Exception as e:
    print(e)
    return {"status": "error"}
  return {"status": "ok"}