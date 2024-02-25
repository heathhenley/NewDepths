""" NOAA CSB/MBES Notification API

An api to subscribe to notifications for new data within a user
defined bounding box. At the moment, only supports MBES data from NOAA,
but will soon be expanded to CSB data.

A worker runs through the database of bounding boxes, checks for new data,
and emails the user about the new data if there is any.
"""
from datetime import timedelta, datetime, timezone
import os
from typing import Annotated

from dotenv import load_dotenv
from fastapi import (
  FastAPI, Form, Depends, HTTPException, status,
  templating, staticfiles, Request
)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session

from db import database, crud, models
from schemas import schemas


load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))

if not all([SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES]):
  raise ValueError("Missing environment variable(s)!")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
models.Base.metadata.create_all(bind=database.engine)
app = FastAPI(
  docs_url="/docs",
  redoc_url=None,
  title="NOAA CSB/MBES Notification API",
  description=__doc__)

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
    username: str = payload.get("sub")
    if username is None:
      raise credentials_exception
    token_data = schemas.TokenData(username=username)
    if not (user := crud.get_user_by_username(db, token_data.username)):
      raise credentials_exception
  except JWTError:
    raise credentials_exception
  return user


def verify_password(plain_password, hashed_password):
  return pwd_context.verify(plain_password, hashed_password)


def hash_password(password):
  return pwd_context.hash(password)


def authenticate_user(db: Session, username: str, password: str):
  user = crud.get_user_by_username(db, username)
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
  if (crud.get_user_by_email(db, user.email)
      or crud.get_user_by_username(db, user.username)):
    raise HTTPException(
      status_code=400,
      detail="Email or username already registered"
    )
  if user.password != user.password_confirm:
    raise HTTPException(
      status_code=400,
      detail="Passwords do not match"
    )
  user_create = schemas.UserCreate(
    hashed_password=hash_password(user.password),
    username=user.username,
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
  user = authenticate_user(db, form_data.username, form_data.password)
  if not user:
    raise HTTPException(
      status_code=400,
      detail="Incorrect username or password"
    )
  # create a jwt token and return it
  access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
  access_token = create_access_token(
    data={"sub": user.username},
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
  return len(password) >= 16


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


@app.get("/")
def index(request: Request, db: Session = Depends(get_db)):
  current_user = None
  try:
    token = request.cookies.get("token")
    current_user = get_user(token, db)
  except (HTTPException, KeyError, AttributeError):
    pass
  return templates.TemplateResponse(
    "index.html", {"request": request, "current_user": current_user})


@app.get("/bbox_form")
def bbox_form(request: Request):
  if request.headers.get("hx-request"):
    return templates.TemplateResponse(
      "partials/save_bbox.html", {"request": request})
  return templates.TemplateResponse(
    "index.html", {"request": request, "bbox_form": "true"})


@app.post("/bbox_form")
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
  crud.create_user_bbox(db, bbox, db_user.id)
  return templates.TemplateResponse(
    "partials/done.html", {"request": request})


@app.get("/login")
def login(request: Request):
  if request.headers.get("hx-request"):
    return templates.TemplateResponse(
      "partials/login.html", {"request": request})
  return templates.TemplateResponse(
    "index.html", {"request": request, "login": "true"})


@app.post("/login")
@limiter.limit("10/minute")
def login(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db)):

  user = authenticate_user(db, username, password)

  if not user:
    return templates.TemplateResponse(
      "index.html", {"request": request, "login": "true"})

  access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
  access_token = create_access_token(
    data={"sub": user.username},
    expires_delta=access_token_expires
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


@app.get("/logout")
def logout(request: Request):
  response = templates.TemplateResponse(
    "index.html", {"request": request})
  response.delete_cookie(key="token")
  return response


@app.get("/register")
def register(request: Request):
  if request.headers.get("hx-request"):
    return templates.TemplateResponse(
      "partials/register.html", {"request": request})
  return templates.TemplateResponse(
    "index.html", {"request": request, "register": "true"})


@app.post("/register")
@limiter.limit("10/minute")
def register(
    request: Request,
    username: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    password_confirm: Annotated[str, Form()],
    db: Session = Depends(get_db)):

  if not username or not email or not password or not password_confirm:
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
        "error": "Password is not strong enough"}
    )

  user_create = schemas.UserCreate(
    hashed_password=hash_password(password),
    username=username,
    email=email,
  )
  crud.create_user(db, user_create)

  # log user in automatically after registering
  user = authenticate_user(db, username, password)
  access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
  access_token = create_access_token(
    data={"sub": user.username},
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

