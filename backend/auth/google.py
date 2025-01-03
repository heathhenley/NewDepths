from base64 import b64encode, b64decode
from dataclasses import dataclass
from datetime import datetime, timedelta
import hmac
import hashlib
import json
import logging
from urllib.parse import urlencode
import uuid

import google.auth.transport.requests as google_request
from google.oauth2 import id_token as google_id_token

from settings import GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI


# TODO - store these in a database or cache and add a cleanup function or TTL
VALID_STATES = set()


@dataclass
class AuthStateToken:
  token: str
  expires: datetime
  data: str = None

  def to_state_str(self):
    serialized = b64encode(json.dumps({
      "token": self.token,
      "expires": self.expires.isoformat(),
      "data": self.data,
    }).encode())
    hash = hmac.new(
      GOOGLE_CLIENT_ID.encode(),
      msg=serialized,
      digestmod=hashlib.sha256).hexdigest()
    return b64encode(f"{serialized.decode()}:{hash}".encode()).decode()

  @staticmethod
  def from_state_str(token: str):
    """ Parse the token from a string and validate it. """
    try:
      decoded = b64decode(token.encode()).decode()
      serialized, hash = decoded.split(":")
      data = json.loads(b64decode(serialized.encode()))
      hmac_incoming = hmac.new(
        GOOGLE_CLIENT_ID.encode(),
        msg=serialized.encode(),
        digestmod=hashlib.sha256
      ).hexdigest() 
      if not hmac.compare_digest(hash, hmac_incoming):
        return None
      return AuthStateToken(
        token=data["token"],
        expires=datetime.fromisoformat(data["expires"]),
        data=data.get("data"),
      )
    except Exception as e:
      print(e)
      return None



def validate_state(state: AuthStateToken) -> bool:
  """ Check if this too old - could happen if they take too long in between
  starting the auth flow and finishing it.
  """
  return state and state.expires > datetime.now()


def generate_google_auth_url():
  """ Generate a google auth url with our client id and redirect uri.

  We also generate a state token to prevent CSRF attacks and to store
  any non sensitive data we need to send to google and get back (like maybe
  where to redirect the user back to after they authenticate - currently not
  being used).

  Returns:
    state: AuthStateToken: The state token to validate the response with.
    url: str: The url to redirect the user to.
  """
  state = AuthStateToken(
    token=str(uuid.uuid4()),
    expires=datetime.now() + timedelta(minutes=5)
  )
  VALID_STATES.add(state.token)

  baseurl = "https://accounts.google.com"
  path = "/o/oauth2/v2/auth"
  params = {
    "client_id": GOOGLE_CLIENT_ID,
    "redirect_uri": GOOGLE_REDIRECT_URI,
    "response_type": "code",
    "scope": "email",
    "state": state.to_state_str(),
  }
  return state, f"{baseurl}{path}?{urlencode(params)}"


def verify_google_id_token(id_token):
  try:
    return google_id_token.verify_oauth2_token(
      id_token, google_request.Request(), GOOGLE_CLIENT_ID)
  except Exception as e:
    print(e)
    return None
