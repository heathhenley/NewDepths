from datetime import datetime, timedelta, timezone
from jose import jwt
from typing import Annotated

from fastapi import (
  APIRouter, Depends, Form, Request, templating
)
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from db import crud
from dependencies.db import get_db
from dependencies.user import get_user_or_redirect
from schemas import schemas
from settings import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES


templates = templating.Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
user_router = APIRouter()


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


def strong_password(password: str):
  """ Check if the password is strong enough. """
  return len(password) >= 8


@user_router.get("/login", include_in_schema=False)
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


@user_router.post("/login", include_in_schema=False)
def login(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db)):

  if not (user := authenticate_user(db, email, password)):
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


@user_router.get("/logout", include_in_schema=False)
def logout(request: Request):
  response = templates.TemplateResponse(
    "index.html", {"request": request})
  response.delete_cookie(key="token")
  return response


@user_router.get("/register", include_in_schema=False)
def register(request: Request):
  if request.headers.get("hx-request"):
    return templates.TemplateResponse(
      "partials/register.html", {"request": request})
  return templates.TemplateResponse(
    "index.html", {"request": request, "register": "true"})


@user_router.post("/register", include_in_schema=False)
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


@user_router.get("/account", include_in_schema=False)
def account(
    request: Request,
    url: str = "/login",
    user: schemas.User = Depends(get_user_or_redirect)):
  return templates.TemplateResponse(
    "account.html", {"request": request, "current_user": user})
