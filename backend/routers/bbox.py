import json
from typing import Annotated

from fastapi import (
  APIRouter, Depends, Form, HTTPException, Response, Request, templating
) 

from sqlalchemy.orm import Session

from db import crud
from dependencies.user import get_user_or_redirect
from dependencies.db import get_db
from schemas import schemas
from settings import DEFAULT_RATE_LIMIT

from limiter import limiter


MAX_BOXES_PER_USER = 5


bbox_router = APIRouter()
templates = templating.Jinja2Templates(directory="templates")


def is_valid_bbox(
    top_left_lat: float,
    top_left_lon: float,
    bottom_right_lat: float,
    bottom_right_lon: float):
  """ Check if the bounding box is valid. """
  # check physical limits
  if any([x < -90 or x > 90 for x in [top_left_lat, bottom_right_lat]]):
    return False
  if any([x < -180 or x > 180 for x in [top_left_lon, bottom_right_lon]]):
    return False
  # max 10 degrees in either direction, same as noaa point store
  if abs(top_left_lat - bottom_right_lat) > 10:
    return False
  if abs(top_left_lon - bottom_right_lon) > 10:
    return False
  # top left should be north and west of bottom right
  return top_left_lat > bottom_right_lat and top_left_lon < bottom_right_lon


@bbox_router.get("/bbox_form", include_in_schema=False)
@limiter.limit(DEFAULT_RATE_LIMIT)
def bbox_form(request: Request):
  if request.headers.get("hx-request"):
    return templates.TemplateResponse(
      "partials/save_bbox.html", {"request": request})
  return templates.TemplateResponse(
    "index.html", {"request": request, "bbox_form": "true"})


@bbox_router.post("/bbox_form", include_in_schema=False)
@limiter.limit(DEFAULT_RATE_LIMIT)
def bbox_form(
    request: Request,
    top_left_lat: Annotated[float, Form()],
    top_left_lon: Annotated[float, Form()],
    bottom_right_lat: Annotated[float, Form()],
    bottom_right_lon: Annotated[float, Form()],
    db: Session = Depends(get_db),
    user: schemas.User = Depends(get_user_or_redirect)):
 
  bbox = schemas.BoundingBox(
    top_left_lat=top_left_lat,
    top_left_lon=top_left_lon,
    bottom_right_lat=bottom_right_lat,
    bottom_right_lon=bottom_right_lon
  )
  if not is_valid_bbox(
      bbox.top_left_lat, bbox.top_left_lon,
      bbox.bottom_right_lat, bbox.bottom_right_lon):
    resp = templates.TemplateResponse(
      "partials/save_bbox.html", {"request": request })
    resp.headers["hx-trigger"] = json.dumps({
      "showAlert": "Bounding box is invalid, or too large."
    })
    return resp

  db_user = crud.get_user_by_email(db, user.email)
  if len(db_user.bboxes) > MAX_BOXES_PER_USER:
    resp = templates.TemplateResponse(
      "partials/save_bbox.html", {"request": request})
    resp.headers["hx-trigger"] = json.dumps({
      "showAlert": f"Max {MAX_BOXES_PER_USER} boxes/user. Delete one to add more."
    })
    return resp

  # good to save bbox
  crud.create_user_bbox(db, bbox, db_user.id)
  resp = templates.TemplateResponse(
    "partials/save_bbox.html", {"request": request}
  )
  resp.headers["hx-trigger"] = json.dumps({
    "showAlert": "Created new bounding box!"
  })
  return resp


@bbox_router.delete("/bboxes/{bbox_id}", include_in_schema=False)
@limiter.limit(DEFAULT_RATE_LIMIT)
def delete_bbox(
    request: Request,
    bbox_id: int,
    user: schemas.User = Depends(get_user_or_redirect),
    db: Session = Depends(get_db)):
  
  # get the orders so we can remove them from the ui and alert
  orders = crud.get_data_orders_by_bbox_id(db, bbox_id)
  if not orders:
    orders = []

  # actually delete the bbox
  if not crud.delete_user_bbox(db, bbox_id, user.id):
    return HTTPException(
      status_code=204,
      detail="Invalid permission, or invalid bbox id"
    )
  
  # alert and trigger event to remove from ui
  resp = Response(status_code=200)
  resp.headers["hx-trigger"] = json.dumps({
    "showAlert": f"Deleted box: {bbox_id} (and {len(orders)} orders)",
    "deletedOrders": [x.id for x in orders]
  })
  return resp
