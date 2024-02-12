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
  FastAPI, Depends, HTTPException, status, Request
)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from db import database, crud, models
from schemas import schemas


load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")

if not all([SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES]):
  raise ValueError("Missing environment variable(s)!")


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
models.Base.metadata.create_all(bind=database.engine)
app = FastAPI(
  docs_url="/",
  redoc_url=None,
  title="NOAA CSB/MBES Notification API",
  description=__doc__)


# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


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
async def read_user_info(
    current_user: schemas.User = Depends(get_user)):
  """ Get the currently authenticated user's info"""
  return current_user


@app.post("/users", response_model=schemas.User, tags=["auth"])
async def create_user(
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
async def login_for_access_token(
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
async def get_bboxes(
   user: schemas.User = Depends(get_user),
   db: Session = Depends(get_db)):
  """ Get all the bounding boxes for this user.

  Returns a 200 if successful, 400 if the token is invalid.
  """
  return crud.get_user_bboxes(db, user.id)


@app.post("/api/bboxes", tags=["notifications"])
async def add_bbox(
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