from urllib.parse import urlencode

import google.auth.transport.requests as google_request
from google.oauth2 import id_token as google_id_token

from settings import GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI


def generate_google_auth_url():
  baseurl = "https://accounts.google.com"
  path = "/o/oauth2/v2/auth"
  params = {
    "client_id": GOOGLE_CLIENT_ID,
    "redirect_uri": GOOGLE_REDIRECT_URI,
    "response_type": "code",
    "scope": "email",
  }
  return f"{baseurl}{path}?{urlencode(params)}"


def verify_google_id_token(id_token):
  try:
    return google_id_token.verify_oauth2_token(
      id_token, google_request.Request(), GOOGLE_CLIENT_ID)
  except Exception as e:
    print(e)
    return None
