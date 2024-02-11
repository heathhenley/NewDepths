from collections import defaultdict
from datetime import datetime
import logging
import os
import requests

import resend
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from db.database import SessionLocal
from db import crud
from db import models

load_dotenv()
resend.api_key = os.getenv("RESEND_KEY")

# This one isn't working at the moment started returning 500s, so getting setup
# using the multibeam service instead
NOAA_MULTIBEAM_URL = r"https://gis.ngdc.noaa.gov/arcgis/rest/services/web_mercator/multibeam_dynamic/MapServer/0/query"


def bbox_to_envelope(bbox: models.BoundingBox) -> str:
  """ Convert a bbox to a string in the correct esri format for 'envelope'."""
  xmin = min(bbox.top_left_lon, bbox.bottom_right_lon)
  xmax = max(bbox.top_left_lon, bbox.bottom_right_lon)
  ymin = min(bbox.top_left_lat, bbox.bottom_right_lat)
  ymax = max(bbox.top_left_lat, bbox.bottom_right_lat)
  return f"{xmin},{ymin},{xmax},{ymax}"

# TODO add since parameter, will reduce the amount of data we need to process
# eg it will only get possble new data
def multibeam_query_params(bbox: models.BoundingBox) -> dict:
  return {
    'f': 'json',
    'where': '',
    'geometry': bbox_to_envelope(bbox),
    'geometryType': 'esriGeometryEnvelope',
    'inSR': 4326,
    'spatialRel': 'esriSpatialRelIntersects',
    'outFields': 'SURVEY_ID,PLATFORM,DOWNLOAD_URL,START_TIME,END_TIME',
    'returnGeometry': False,
    'orderByFields': 'START_TIME'
  }


def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()


def get_data_for_bbox(
    url: str, query_params: dict, bbox: models.BoundingBox) -> str | None:
  """ Make the actual request to the NOAA API. """
  try:
    res = requests.get(url, params=query_params, timeout=5)
    if res.status_code != 200:
      raise Exception(f"Bad response from NOAA: {res.status_code}")
  except Exception as e:
    print(f"Error getting data for bbox {bbox.id}: {e}")
    return None
  return res.json()


def make_email_body(notifications):
  """ Make the email body for the user. """
  body = "<h1> New data found for your bounding boxes! </h1>"
  for notification in notifications:
    bbox = notification["bbox_id"]
    data_type = notification["data_type"]
    new_surveys = notification["new_surveys"]
    body += f"<h2> New '{data_type.name}' data for bbox #{bbox.id} </h2>"
    body += (
      f"<h3>BBOX: ({bbox.top_left_lat:.2f}, {bbox.top_left_lon:.2f}), "
      f"({bbox.bottom_right_lat:.2f}, {bbox.bottom_right_lon:.2f})</h3>"
    )
    body += f"<p>There are {len(new_surveys)} new surveys for this box.</p>"
    body += "<ul>"
    for survey in new_surveys[:5]:
      sid = survey["attributes"]["SURVEY_ID"]
      pf = survey["attributes"]["PLATFORM"]
      dl = survey["attributes"]["DOWNLOAD_URL"]
      body += f"<li>ID: {sid}, platform: {pf}, <a href={dl}>Link</a></li>"
    body += "</ul>"
    if len(new_surveys) > 5:
      body += f"<p>And {len(new_surveys) - 5} more...</p>"
  return body


def check_for_new_data(
    db: Session,
    bboxes: list[models.BoundingBox],
    data_types: list[models.DataType]) -> dict[int, list]:
  """ Check for new data for each bounding box and data type. """

  notifications_by_user = defaultdict(list)
  for bbox in bboxes:
    for data_type in data_types:

      print(f"Getting updates for: {data_type.name}")

      # get the last cached date for this bbox
      date = crud.get_last_cached_date(db, bbox, data_type)
      print(f"Update bbox {bbox.id}, "
            f"for data type {data_type.name}, "
            f"last data from: {date}")

      # TODO generalize, use since date to reduce the amount of data
      query_params = multibeam_query_params(bbox)

      url = data_type.base_url
      if not (new_data := get_data_for_bbox(url, query_params, bbox)):
        print(f"No new data for bbox {bbox.id}")
        continue

      if not (surveys := new_data['features']):
        print(f"No new data for bbox {bbox.id}")
        continue

      # get the latest date from the new data, this will be cached 
      latest_date = surveys[-1]["attributes"]["START_TIME"] # it's sorted
      latest_datetime = datetime.fromtimestamp(latest_date / 1000.0)
      print(f"Latest date for bbox {bbox.id}: {latest_datetime}")

      if date is not None:
        surveys = [
          s for s in surveys
          if s["attributes"]["START_TIME"] / 1000.0 > date.timestamp()
        ]

      print(f"BBOX: {bbox.id} has {len(surveys)} "
            f"new {data_type.name} surveys since {date}.")
      
      # upsert in the database
      crud.set_last_cached_date(db, bbox, data_type, latest_datetime)

      # add to the notifications list for later
      if surveys:
        notifications_by_user[bbox.owner_id].append(
          {
            "bbox_id": bbox,
            "data_type": data_type,
            "new_surveys": surveys
          }
        )
  return notifications_by_user


def main():
  logging.basicConfig(level=logging.DEBUG)

  db = next(get_db())

  if not db or not db.query(models.User).count():
    logging.error("No connection to the database or no users found. Exiting.")
    return 1

  # drop and recreate the cache table for testing
  models.CacheBoundingBoxUpdate.__table__.drop(db.bind)
  models.CacheBoundingBoxUpdate.__table__.create(db.bind)
  # add type for testing
  if not db.query(models.DataType).count():
    db.add(models.DataType(
      name="multibeam",
      base_url=NOAA_MULTIBEAM_URL,
      description="NOAA Multibeam Data"
    ))
    db.commit()


  data_types = crud.get_data_types(db)
  bboxes = crud.get_all_bboxes(db)

  # we want to only notify each user once, so we'll use a defaultdict and track
  # all the new stuff they're interested in, then we can send just one
  # notification / email to each user
  notifications_by_user = check_for_new_data(db, bboxes, data_types)

  # send the notifications
  for user_id, notifications in notifications_by_user.items():

    user = crud.get_user_by_id(db, user_id)

    if not user or not user.email:
      logging.error(f"User {user_id} not found or has no email.")
      continue

    logging.info(f"Sending notifications to {user.email}.")

    email_body = make_email_body(notifications)
    r = resend.Emails.send({
      "from": "onboarding@resend.dev",
      "to": user.email,
      "subject": "There is new NOAA data available!",
      "html": email_body
    })
    logging.info(f"Email sent to {user.id} with status: {r.status_code}")





if __name__ == "__main__":
  main()
