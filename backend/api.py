""" NewDepths.xyz Bathymetry Data Notification API/Server

An api and simple frontend to subscribe to notifications for new data within a
user defined bounding box. At the moment, supports MBES, NOS, and CSB data from
NOAA.

A worker runs through the database of bounding boxes, checks for new data,
and emails the user about the new data if there is any. The user can also order
new data from the new NOAA point store api.

Written like this to get a chance to play with HTMX, roll my own auth, and take
a break from the js/ts frameworks-of-the-day. Though it's still going to have
a little bit of js because of all the interaction with the map.
"""
from fastapi import (
  FastAPI, Depends, HTTPException,
  templating, staticfiles, Request
)
from jose import jwt
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session

from db import database, models
from dependencies.user import get_user_or_none
from dependencies.db import get_db
from limiter import limiter

# The routers
from routers.ricky import rick_roll_router
from routers.noaa import noaa_router
from routers.bbox import bbox_router
from routers.user import user_router
from routers.google_auth import generate_google_auth_url, google_auth_router


models.Base.metadata.create_all(bind=database.engine)

# the main app object
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

# static files and templates
app.mount("/static", staticfiles.StaticFiles(directory="static"), name="static")
templates = templating.Jinja2Templates(directory="templates")


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# The main route - where it all starts
@app.get("/", include_in_schema=False)
@limiter.limit("10/minute")
def index(request: Request, db: Session = Depends(get_db) ):
  current_user = None
  try:
    current_user = get_user_or_none(request.cookies.get("token"), db)
  except (HTTPException, KeyError, AttributeError):
    pass
  return templates.TemplateResponse(
    "index.html",
    {
      "request": request,
      "current_user": current_user,
    })


# User login/logout/register/account routes
app.include_router(user_router)

# Routes related to third party auth (google)
app.include_router(google_auth_router)

# Create and delete bounding boxes
app.include_router(bbox_router)

# Submit orders to NOAA
app.include_router(noaa_router)

# Catch all route for the rick roll
# NOTE: this needs to be the last route in the file
app.include_router(rick_roll_router)
