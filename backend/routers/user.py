from datetime import timedelta
from typing import Annotated

from fastapi import (
  APIRouter, Depends, Form, Request, templating
)
from sqlalchemy.orm import Session

from auth.base import (
  authenticate_user, create_access_token, hash_password, strong_password
)
from auth.google import generate_google_auth_url
from db import crud
from dependencies.db import get_db
from dependencies.user import get_user_or_redirect
from schemas import schemas
from settings import ACCESS_TOKEN_EXPIRE_MINUTES, DEFAULT_RATE_LIMIT

from limiter import limiter


templates = templating.Jinja2Templates(directory="templates")
user_router = APIRouter()


@user_router.get("/login", include_in_schema=False)
@limiter.limit(DEFAULT_RATE_LIMIT)
def login(request: Request):
  if request.headers.get("hx-request"):
    response = templates.TemplateResponse(
      "partials/login.html",
      {
        "request": request,
        "google_auth_url": generate_google_auth_url()
      })
    response.headers["vary"] = "hx-request"
    return response
  response = templates.TemplateResponse(
    "index.html", {
      "request": request,
      "login": "true",
      "google_auth_url": generate_google_auth_url()
    }
  )
  response.headers["vary"] = "hx-request"
  return response


@user_router.post("/login", include_in_schema=False)
@limiter.limit(DEFAULT_RATE_LIMIT)
def login(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db)):

  if not (user := authenticate_user(db, email, password)):
    return templates.TemplateResponse("index.html",
      {"request": request,
       "login": "true",
       "error": "Invalid credentials",
       "google_auth_url": generate_google_auth_url()
      }
    )

  access_token = create_access_token(
    data={"sub": user.email},
    expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
  )
  response = templates.TemplateResponse(
      "index.html",
      {
        "request": request,
        "current_user": user,
        "google_auth_url": generate_google_auth_url()
      }
  )
  response.set_cookie(
    key="token",
    value=access_token,
    httponly=True,
    secure=True,
    max_age=60*int(ACCESS_TOKEN_EXPIRE_MINUTES)
  )
  return response


@user_router.get("/logout", include_in_schema=False)
@limiter.limit(DEFAULT_RATE_LIMIT)
def logout(request: Request):
  response = templates.TemplateResponse(
    "index.html", {"request": request})
  response.delete_cookie(key="token")
  return response


@user_router.get("/register", include_in_schema=False)
@limiter.limit(DEFAULT_RATE_LIMIT)
def register(request: Request):
  if request.headers.get("hx-request"):
    return templates.TemplateResponse(
      "partials/register.html",
      {
        "request": request,
        "google_auth_url": generate_google_auth_url()
      })
  return templates.TemplateResponse(
    "index.html",
    {
      "request": request,
      "register": "true",
      "google_auth_url": generate_google_auth_url()
    })


@user_router.post("/register", include_in_schema=False)
@limiter.limit(DEFAULT_RATE_LIMIT)
def register(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    password_confirm: Annotated[str, Form()],
    db: Session = Depends(get_db)):

  google_url = generate_google_auth_url()

  if not email or not password or not password_confirm:
    return templates.TemplateResponse(
      "index.html", {
        "request": request,
        "register": "true",
        "error": "All fields are required",
        "google_auth_url": google_url
      }
    )

  if (crud.get_user_by_email(db, email)):
    return templates.TemplateResponse(
      "index.html", {
        "request": request,
        "register": "true",
        "error": "Email already registered",
        "google_auth_url": google_url
      }
    )

  if password != password_confirm:
    return templates.TemplateResponse(
      "index.html", {
        "request": request,
        "register": "true",
        "error": "Passwords do not match",
        }
    )

  if not strong_password(password):
    return templates.TemplateResponse(
      "index.html", {
        "request": request,
        "register": "true",
        "error": "Password must be at least 8 characters long",
        "google_auth_url": google_url}
    )

  user_create = schemas.UserCreate(
    hashed_password=hash_password(password),
    email=email,
  )
  if not (crud.create_user(db, user_create)):
    return templates.TemplateResponse(
      "index.html", {
        "request": request,
        "register": "true",
        "error": "Error creating user",
        "google_auth_url": google_url
      }
    )

  # DRY this out
  # log user in automatically after registering
  user = authenticate_user(db, email, password)
  access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
  access_token = create_access_token(
    data={"sub": user.email},
    expires_delta=access_token_expires
  )
  request = templates.TemplateResponse(
      "index.html", {
        "request": request,
        "current_user": user,
        "google_auth_url": google_url
      }
    )
  request.set_cookie(
    key="token",
    value=access_token,
    httponly=True,
    secure=True,
    max_age=60*int(ACCESS_TOKEN_EXPIRE_MINUTES)
  )
  return request


@user_router.get("/account", include_in_schema=False)
@limiter.limit(DEFAULT_RATE_LIMIT)
def account(
    request: Request,
    url: str = "/login",
    user: schemas.User = Depends(get_user_or_redirect)):
  return templates.TemplateResponse(
    "account.html", {"request": request, "current_user": user})
