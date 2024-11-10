from datetime import timedelta
import logging
import requests

from fastapi import (
  APIRouter, Depends, Request, templating, HTTPException, status
)
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from auth.base import create_access_token
from auth.google import (
  AuthStateToken, 
  generate_google_auth_url,
  validate_state,
  verify_google_id_token,
)
from db import crud
from dependencies.db import get_db
from limiter import limiter
from schemas import schemas
from settings import (
  GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI, GOOGLE_CLIENT_SECRET,
  ACCESS_TOKEN_EXPIRE_MINUTES, DEFAULT_RATE_LIMIT
)

templates = templating.Jinja2Templates(directory="templates")
google_auth_router = APIRouter()


@google_auth_router.get("/googleauth/authorize")
@limiter.limit(DEFAULT_RATE_LIMIT)
def google_auth_authorize(request: Request, db: Session = Depends(get_db)):
  """ Redirect the user to the Google OAuth consent screen. """
  state, url = generate_google_auth_url()
  response = RedirectResponse(
    url=url,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
  )
  response.set_cookie(
    key="state",
    value=state.to_state_str(),
    httponly=True,
    secure=True,
    max_age=60*5
  )
  return response



# These are the endpoints to implement Google OAuth flow
@google_auth_router.get("/googleauth/callback")
@limiter.limit(DEFAULT_RATE_LIMIT)
def google_auth_callback(
  request: Request,
  code: str = None,
  state: str = None,
  error: str = None,
  db: Session = Depends(get_db),
):
  """ Exchange the authorization code for an access token and id token.

    The id_token is a JWT that contains the users email, avatar link, etc. We
    only care about the email, and sub (a unique google id for the user). We don't
    need to make anymore requests to the google api so we're not even going to
    store the access token.
  """
  if error:
    raise HTTPException(
      status_code=status.HTTP_307_TEMPORARY_REDIRECT,
      detail=f"Failed to authenticate with Google\n{error}",
      headers={"Location": "/login"})
  
  if not state or not (parsed_state := AuthStateToken.from_state_str(state)):
    logging.error("No state or invalid state - possible CSRF attack")
    raise HTTPException(
      status_code=status.HTTP_307_TEMPORARY_REDIRECT,
      detail="Failed to authenticate with Google",
      headers={"Location": "/login"})
  
  if state != request.cookies.get("state"):
    logging.error("State mismatch - possible CSRF attack")
    raise HTTPException(
      status_code=status.HTTP_307_TEMPORARY_REDIRECT,
      detail="Failed to authenticate with Google",
      headers={"Location": "/login"})

  if not validate_state(parsed_state):
    logging.error("State expired")
    raise HTTPException(
      status_code=status.HTTP_307_TEMPORARY_REDIRECT,
      detail="Failed to authenticate with Google",
      headers={"Location": "/login"})

  # If we're here, the state checks out and we're ready to exchange the code 
  # for an access token and id token
  data = {
    'code': code,
    'client_id': GOOGLE_CLIENT_ID, 
    'client_secret': GOOGLE_CLIENT_SECRET,
    'redirect_uri': GOOGLE_REDIRECT_URI,
    'grant_type': 'authorization_code'
  }
  try:
    r = requests.post(
      'https://oauth2.googleapis.com/token',
      data=data,
      timeout=5
    )

    if r.status_code != 200:
      logging.error(f"Failed to get token from google: {r.text}")
      raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail="Failed to authenticate with Google",
        headers={"Location": "/login"})
  except Exception as e:
    logging.critical(f"Failed to get token from google: {e}")
    raise HTTPException(
      status_code=status.HTTP_307_TEMPORARY_REDIRECT,
      detail="Failed to authenticate with Google",
      headers={"Location": "/login"})


  # Parse the JWT to get info (also verify but we know it's from google)
  if not (info := verify_google_id_token(r.json()['id_token'])):
    raise HTTPException(
      status_code=status.HTTP_307_TEMPORARY_REDIRECT,
      detail="Failed to authenticate with Google",
      headers={"Location": "/login"}) 

  email, sub = info['email'], info['sub']

  # get the user by email (they may have logged in before)
  if user := crud.get_user_by_email(db, email):
    if not user.google_sub:
      # update the user with the google sub, if it's not already there
      user.google_sub = sub
      db.commit()

  # try get the user by google sub if we didn't find them by email
  # otherwise create a new user
  if not user and not (user := crud.get_user_by_google_sub(db, sub)):
    # create a new user
    user = crud.create_user(
      db, schemas.UserCreate(email=email, google_sub=sub))

  # Log them in and redirect to the index page
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
    secure=True,
    max_age=60*int(ACCESS_TOKEN_EXPIRE_MINUTES)
  )
  return response
  