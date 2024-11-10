import requests
from urllib.parse import urlencode

from fastapi import (
  APIRouter, Depends, Request, templating
)
from google.auth.transport import requests as google_request
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from dependencies.db import get_db
from limiter import limiter
from settings import GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI, GOOGLE_CLIENT_SECRET

templates = templating.Jinja2Templates(directory="templates")
google_auth_router = APIRouter()


def generate_google_auth_url():
  baseurl = "https://accounts.google.com"
  path = "/o/oauth2/v2/auth"
  params = {
    "client_id": GOOGLE_CLIENT_ID,
    "redirect_uri": GOOGLE_REDIRECT_URI,
    "response_type": "code",
    "scope": "email",
  }
  # build the url with the params
  url = f"{baseurl}{path}?{urlencode(params)}"
  print("url", url)
  return url

# These are the endpoints to implement Google OAuth flow
@google_auth_router.get("/googleauth/callback")
def google_auth_callback(
  request: Request,
  code: str,
  db: Session = Depends(get_db),
):
  # exchange the code for an access token
  print("code", code)
  # exchange the code for an access token
  data = {
    'code': code,
    'client_id': GOOGLE_CLIENT_ID, 
    'client_secret': GOOGLE_CLIENT_SECRET,
    'redirect_uri': GOOGLE_REDIRECT_URI,
    'grant_type': 'authorization_code'
  }
  r = requests.post('https://oauth2.googleapis.com/token', data=data)
  if r.status_code != 200:
    return "Error"

  id_ = r.json()['id_token']

  try:
    info = id_token.verify_oauth2_token(
      id_, google_request.Request(), GOOGLE_CLIENT_ID)
    for key, value in info.items():
      print(key, value)
  except Exception as e:
    print(e)
    return "Error"
  # put the info in the db we need in the db (email, picture link, sub [it's a
  # unique identifier for the user])
  # set the id token in a secure http only cookie
  # return the user to the main page
  return "OK"