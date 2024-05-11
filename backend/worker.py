from collections import defaultdict
import logging
import os

import resend
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from db.database import SessionLocal
from db import crud, models
from fetchers.data_fetchers import data_fetcher_factory, SurveyDataList


load_dotenv()
resend.api_key = os.getenv("RESEND_KEY")


def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()


# TODO Make this a jinja2 template
def make_email_body(notifications: SurveyDataList):
  """ Make the email body for the user. """
  body = "<h1> New data found for your bounding boxes! </h1>"
  for notification in notifications:
    bbox = notification.bbox
    data_type = notification.description
    json_url = notification.json_url
    new_surveys = notification.data

    body += f"<h2> New '{data_type}' data for bbox</h2>"
    body += (
      f"<h3>BBOX: ({bbox.top_left_lat:.2f}, {bbox.top_left_lon:.2f}), "
      f"({bbox.bottom_right_lat:.2f}, {bbox.bottom_right_lon:.2f})</h3>"
    )
    body += f"<p>There are {len(new_surveys)} new surveys for this box.</p>"
    body += "<ul>"
    for survey in new_surveys[:5]:
      body += f"<li>{survey.time}"
      body += f", Platform: {survey.platform}"
      dl = survey.download_url
      if dl:
        body += f", <a href={dl}>Link</a></li>"
    body += "</ul>"
    if len(new_surveys) > 5:
      body += f"<p>And {len(new_surveys) - 5} more...</p>"
    body += f'<a href={json_url}> API CALL (full JSON results) </a><br/>'
    body += f'<a href=https://newdepths.xyz/account> Order data from noaa from your account</a>'
  body += """
    <p style="color:gray;font-size:0.75rem">Thanks for using NewDepths.xyz! - I
    haven't implemented a way to unsubscribe / delete your account yet. If 
    that's something you want to do, just reply to this email and I'll take 
    care of it.</p>"""
  return body


def check_for_new_data(
    db: Session,
    bboxes: list[models.BoundingBox],
    data_types: list[models.DataType]) -> dict[int, list]:
  """ Check for new data for each bounding box and data type. """

  notifications_by_user = defaultdict(list)

  for data_type in data_types:

    fetcher = data_fetcher_factory(data_type)

    for bbox in bboxes:

      # get the last cached date for this bbox
      date = crud.get_last_cached_date(db, bbox, data_type)

      logging.info(f"Update bbox {bbox.id}, "
            f"for data type {data_type.name}, "
            f"last data from: {date}")
      
      if not (results := fetcher.get_data(bbox, date)):
        continue

      latest_datetime = results.get_latest_datetime()
      logging.info(f"Latest date for bbox {bbox.id}: {latest_datetime}")

      # filter out any surveys that are older than the last cached date
      if date is not None:
        surveys = [s for s in results.data if s.time > date]
        results.data = surveys

      # upsert in the database
      crud.set_last_cached_date(db, bbox, data_type, latest_datetime)

      if results.data:
        notifications_by_user[bbox.owner_id].append(results)

  return notifications_by_user


def main():
  logging.basicConfig(level=logging.INFO)

  db = next(get_db())

  if not db or not db.query(models.User).count():
    logging.error("No connection to the database or no users found. Exiting.")
    return 1

  data_types = crud.get_data_types(db)
  bboxes = crud.get_all_bboxes(db)

  if not data_types or not bboxes:
    logging.error("No data types or bounding boxes found. Exiting.")
    return 1
  
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
      "from": "data@updates.newdepths.xyz",
      "reply_to": "data@newdepths.xyz",
      "to": user.email,
      "subject": "There is new NOAA data available!",
      "html": email_body
    })
    logging.info(f"Email sent to {user.id} (result: {r})")


if __name__ == "__main__":
  main()
