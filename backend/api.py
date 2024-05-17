""" NewDepths.xyz Bathymetry Data Notification API/Server

An api and simple frontend to subscribe to notifications for new data within a
user defined bounding box. At the moment, supports MBES, NOS, and CSB data from
NOAA.

A worker runs through the database of bounding boxes, checks for new data,
and emails the user about the new data if there is any. The user can also order
new data from the new NOAA point store api.

Written like this to get a chance to play with HTMX, roll my own auth, and take
a break from the js/ts frameworks-of-the-day. Though it's still going to have
a little bit of js because of all the interactiion with the map, would be good
to add some toasts, etc.
"""
from datetime import timedelta, datetime, timezone
import os
import requests
from typing import Annotated

from dotenv import load_dotenv
from fastapi import (
  FastAPI, Form, Depends, HTTPException, status,
  templating, staticfiles, Request, Response
)
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session

from db import database, crud, models
from schemas import schemas


MAX_BOXES_PER_USER = 5

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

if not all([SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES]):
  raise ValueError("Missing environment variable(s)!")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
  docs_url="/docs",
  redoc_url=None,
  title="NOAA CSB/MBES Notification API",
  description=__doc__,
  contact={
    "name": "Heath Henley",
    "email": "heath@newdepths.xyz"
  },
  license_info={
    "name": "MIT License",
    "url": "https://opensource.org/licenses/MIT"
  }
)

app.mount("/static", staticfiles.StaticFiles(directory="static"), name="static")

templates = templating.Jinja2Templates(directory="templates")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# DB Dependency
def get_db():
  db = database.SessionLocal()
  try:
    yield db
  finally:
    db.close()


# Gets the user from JWT in header if it exists
def get_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db)):
  credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"}
  )
  try:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    email: str = payload.get("sub")
    if email is None:
      raise credentials_exception
    token_data = schemas.TokenData(email=email)
    if not (user := crud.get_user_by_email(db, token_data.email)):
      raise credentials_exception
  except JWTError:
    raise credentials_exception
  return user


def verify_password(plain_password, hashed_password):
  return pwd_context.verify(plain_password, hashed_password)


def hash_password(password):
  return pwd_context.hash(password)


def authenticate_user(db: Session, email: str, password: str):
  user = crud.get_user_by_email(db, email)
  if not user:
    return False
  if not verify_password(password, user.hashed_password):
    return False
  return user


def create_access_token(data: dict, expires_delta: timedelta):
  to_encode = data.copy()
  expire = datetime.now(timezone.utc) + expires_delta
  to_encode.update({"exp": expire})
  encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
  return encoded_jwt


@app.get("/users/me", response_model=schemas.User, tags=["auth"])
def read_user_info(
    current_user: schemas.User = Depends(get_user)):
  """ Get the currently authenticated user's info"""
  return current_user


@app.post("/users", response_model=schemas.User, tags=["auth"])
@limiter.limit("10/minute")
def create_user(
    request: Request,
    user: schemas.UserFromForm,
    db: Session = Depends(get_db)):
  """ Create a new user.

  Returns a 201 if successful, 400 if there was an error.
  """
  if crud.get_user_by_email(db, user.email):
    raise HTTPException(
      status_code=400,
      detail="Email already registered"
    )
  if user.password != user.password_confirm:
    raise HTTPException(
      status_code=400,
      detail="Passwords do not match"
    )
  user_create = schemas.UserCreate(
    hashed_password=hash_password(user.password),
    email=user.email,
    full_name=user.full_name
  )
  return crud.create_user(db, user_create)


@app.post("/token", tags=["auth"])
@limiter.limit("10/minute")
def login_for_access_token(
   request: Request,
   form_data: OAuth2PasswordRequestForm = Depends(),
   db: Session = Depends(get_db)):
  # try to get the user from the database
  user = authenticate_user(db, form_data.email, form_data.password)
  if not user:
    raise HTTPException(
      status_code=400,
      detail="Incorrect username or password"
    )
  # create a jwt token and return it
  access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
  access_token = create_access_token(
    data={"sub": user.email},
    expires_delta=access_token_expires
  )
  return schemas.Token(access_token=access_token, token_type="bearer")


# TODO: add bbox area limit?
def is_valid_bbox(
    top_left_lat: float,
    top_left_lon: float,
    bottom_right_lat: float,
    bottom_right_lon: float):
  """ Check if the bounding box is valid. """
  return top_left_lat > bottom_right_lat and top_left_lon < bottom_right_lon


def strong_password(password: str):
  """ Check if the password is strong enough. """
  return len(password) >= 8


@app.get(
    "/api/datatypes",
    tags=["notifications"],
    response_model=list[schemas.DataTypes])
def get_datatypes(db: Session = Depends(get_db)):
  """ List the available data types for notifications.

  They correspond to different data sources at NOAA.
  """
  return crud.get_data_types(db)


@app.get("/api/bboxes", tags=["notifications"])
def get_bboxes(
   user: schemas.User = Depends(get_user),
   db: Session = Depends(get_db)):
  """ Get all the bounding boxes for this user.

  Returns a 200 if successful, 400 if the token is invalid.
  """
  return crud.get_user_bboxes(db, user.id)


@app.post("/api/bboxes", tags=["notifications"])
@limiter.limit("10/minute")
def add_bbox(
  request: Request,
  bbox: schemas.BoundingBox,
  user: Annotated[schemas.User, Depends(get_user)],
  db: Session = Depends(get_db)):
  """ Add a bounding box for notification to the database for this user.

  Returns a 201 if successful, 400 if the bounding box is invalid.
  """
  if not is_valid_bbox(
      bbox.top_left_lat, bbox.top_left_lon,
      bbox.bottom_right_lat, bbox.bottom_right_lon):
    raise HTTPException(
      status_code=400,
      detail="Invalid bounding box"
    )
  db_user = crud.get_user_by_email(db, user.email)
  crud.create_user_bbox(db, bbox, db_user.id)
  return {"message": "New bounding box added!"}


@app.get("/", include_in_schema=False)
@limiter.limit("60/minute")
def index(request: Request, db: Session = Depends(get_db)):
  current_user = None
  try:
    token = request.cookies.get("token")
    current_user = get_user(token, db)
  except (HTTPException, KeyError, AttributeError):
    pass
  return templates.TemplateResponse(
    "index.html", {"request": request, "current_user": current_user})


@app.get("/bbox_form", include_in_schema=False)
def bbox_form(request: Request):
  if request.headers.get("hx-request"):
    return templates.TemplateResponse(
      "partials/save_bbox.html", {"request": request})
  return templates.TemplateResponse(
    "index.html", {"request": request, "bbox_form": "true"})


@app.post("/bbox_form", include_in_schema=False)
@limiter.limit("10/minute")
def bbox_form(
    request: Request,
    top_left_lat: Annotated[float, Form()],
    top_left_lon: Annotated[float, Form()],
    bottom_right_lat: Annotated[float, Form()],
    bottom_right_lon: Annotated[float, Form()],
    db: Session = Depends(get_db)):
  try:
    token = request.cookies.get("token")
    user = get_user(token, db)
  except (HTTPException, KeyError):
    return templates.TemplateResponse("partials/not_logged_in.html", {"request": request})
  
  bbox = schemas.BoundingBox(
    top_left_lat=top_left_lat,
    top_left_lon=top_left_lon,
    bottom_right_lat=bottom_right_lat,
    bottom_right_lon=bottom_right_lon
  )
  if not is_valid_bbox(
      bbox.top_left_lat, bbox.top_left_lon,
      bbox.bottom_right_lat, bbox.bottom_right_lon):
    return templates.TemplateResponse(
      "partials/save_bbox.html",
      {"request": request, "error": "Invalid bounding box"})

  db_user = crud.get_user_by_email(db, user.email)
  if len(db_user.bboxes) > MAX_BOXES_PER_USER:
    return templates.TemplateResponse(
      "partials/save_bbox.html",
      {"request": request,
       "error": f"You can only have {MAX_BOXES_PER_USER} bounding boxes"})

  # good to save bbox
  crud.create_user_bbox(db, bbox, db_user.id)
  return templates.TemplateResponse(
    "partials/save_bbox.html", {"request": request}
  )


@app.get("/login", include_in_schema=False)
def login(request: Request):
  if request.headers.get("hx-request"):
    response = templates.TemplateResponse(
      "partials/login.html", {"request": request})
    response.headers["vary"] = "hx-request"
    return response
  response = templates.TemplateResponse(
    "index.html", {"request": request, "login": "true"})
  response.headers["vary"] = "hx-request"
  return response


@app.post("/login", include_in_schema=False)
@limiter.limit("10/minute")
def login(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db)):

  user = authenticate_user(db, email, password)

  if not user:
    return templates.TemplateResponse("index.html",
      {"request": request,
       "login": "true",
       "error": "Invalid credentials"})

  access_token = create_access_token(
    data={"sub": user.email},
    expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
  )
  response = templates.TemplateResponse(
      "index.html", {"request": request, "current_user": user})
  response.set_cookie(
    key="token",
    value=access_token,
    httponly=True,
    max_age=60*int(ACCESS_TOKEN_EXPIRE_MINUTES)
  )
  return response


@app.get("/logout", include_in_schema=False)
def logout(request: Request):
  response = templates.TemplateResponse(
    "index.html", {"request": request})
  response.delete_cookie(key="token")
  return response


@app.get("/register", include_in_schema=False)
@limiter.limit("10/minute")
def register(request: Request):
  if request.headers.get("hx-request"):
    return templates.TemplateResponse(
      "partials/register.html", {"request": request})
  return templates.TemplateResponse(
    "index.html", {"request": request, "register": "true"})


@app.post("/register", include_in_schema=False)
@limiter.limit("10/minute")
def register(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    password_confirm: Annotated[str, Form()],
    db: Session = Depends(get_db)):

  if not email or not password or not password_confirm:
    return templates.TemplateResponse(
      "index.html", {
        "request": request,
        "register": "true",
        "error": "All fields are required"}
    )

  if (crud.get_user_by_email(db, email)):
    return templates.TemplateResponse(
      "index.html", {
        "request": request,
        "register": "true",
        "error": "Email already registered"}
    )

  if password != password_confirm:
    return templates.TemplateResponse(
      "index.html", {
        "request": request,
        "register": "true",
        "error": "Passwords do not match"}
    )

  if not strong_password(password):
    return templates.TemplateResponse(
      "index.html", {
        "request": request,
        "register": "true",
        "error": "Password must be at least 8 characters long"}
    )

  user_create = schemas.UserCreate(
    hashed_password=hash_password(password),
    email=email,
  )
  crud.create_user(db, user_create)

  # log user in automatically after registering
  user = authenticate_user(db, email, password)
  access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
  access_token = create_access_token(
    data={"sub": user.email},
    expires_delta=access_token_expires
  )
  request = templates.TemplateResponse(
      "index.html", {"request": request, "current_user": user})
  request.set_cookie(
    key="token",
    value=access_token,
    httponly=True,
    max_age=60*int(ACCESS_TOKEN_EXPIRE_MINUTES)
  )
  return request

@app.get("/account", include_in_schema=False)
def account(request: Request, db: Session = Depends(get_db)):
  try:
    token = request.cookies.get("token")
    user = get_user(token, db)
  except (HTTPException, KeyError, AttributeError):
    # redirect to home if not logged in
    return RedirectResponse("/")
  return templates.TemplateResponse(
    "account.html", {"request": request, "current_user": user})
  
@app.delete("/bboxes/{bbox_id}", include_in_schema=False)
@limiter.limit("10/minute")
def delete_bbox(
    request: Request,
    bbox_id: int,
    db: Session = Depends(get_db)):
  try:
    token = request.cookies.get("token")
    user = get_user(token, db)
  except (HTTPException, KeyError):
    return HTTPException(
      status_code=204,
    )
  if not crud.delete_user_bbox(db, bbox_id, user.id):
    return HTTPException(
      status_code=204,
      detail="Invalid permission, or invalid bbox id"
    )
  return Response(status_code=200) 


def bbox_to_flat(bbox: models.BoundingBox):
  # their convention is southwest corner to northeast corner, with lon first
  return (f"{bbox.top_left_lon},{bbox.bottom_right_lat},"
          f"{bbox.bottom_right_lon},{bbox.top_left_lat}")


def send_order_to_noaa(
    bbox: models.BoundingBox,
    data_type: str,
    user: models.User):
  """ Send an order to NOAA for data within the bounding box. """
  points_url = f"https://q81rej0j12.execute-api.us-east-1.amazonaws.com/order"
  resp = requests.post(
    points_url,
    headers={"Content-Type": "application/json"},
    json={
      "bbox": bbox_to_flat(bbox), 
      "email": user.email,
      "datasets": [
        {
          "type": data_type
        },
      ]
    }
  )
  if not resp.ok:
    print(resp.json())
    raise Exception("Error sending order to NOAA")
  return resp.json()


@app.get("/order/{bbox_id}/{data_type}", include_in_schema=False)
def order(
    request: Request,
    bbox_id: int,
    data_type: str = "csb",
    db: Session = Depends(get_db)):
  
  if not request.headers.get("hx-request"):
    return RedirectResponse("/account")

  try:
    token = request.cookies.get("token")
    user = get_user(token, db)
  except (HTTPException, KeyError, AttributeError):
    # redirect to home if not logged in
    # TODO: maybe redirect param so they can get redirected after login?
    return RedirectResponse("/login")
  
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
    print(e)
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


def bucket_to_url(bucket_location: str):
  base = "https://order-pickup.s3.amazonaws.com" 
  uuid = bucket_location.split("/")[-1]
  return f"{base}/{uuid}"


def prettier_status(status: str, url: str):
  if status == "complete":
    link = f"<a class='underline' href='{url}'>Download</a>" if url else ""
    return f"Complete! {link}"
  if status == "created":
    return "Created"
  if status == "initialized":
    return "Initialized"
  return "Order status unknown"


@app.get("/order_status/{order_id}", include_in_schema=False)
def order_status(
    request: Request,
    order_id: int,
    db: Session = Depends(get_db)) -> str:
  
  if not request.headers.get("hx-request"):
    return RedirectResponse("/account")
  
  try:
    token = request.cookies.get("token")
    user = get_user(token, db)
  except (HTTPException, KeyError, AttributeError):
    # redirect to home if not logged in
    return RedirectResponse("/login")
  
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
      print(e)
      order.last_status = prettier_status("unknown", None)
    db.commit()

  # assuming we want to stop by default - so far I have only seen complete and
  # and initialized statuses, created is mine
  # so this only keeps going in the cases where I've seen that it should so far
  http_status = 286 # 286 is a custom htmx status code to stop polling
  if any([x in order.last_status.lower() for x in ["created", "initialized"]]):
    http_status = 200  # tells htmx to continue polling
  
  return HTMLResponse(
    order.last_status,
    status_code=http_status
  )
