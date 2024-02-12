from sqlalchemy.orm import Session
from sqlalchemy import DateTime

from db import models
from schemas import schemas


def get_user_by_id(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str):
  return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_username(db: Session, username: str):
  return db.query(models.User).filter(models.User.username == username).first()


def get_users(db: Session, skip: int = 0, limit: int = 100):
  return db.query(models.User).offset(skip).limit(limit).all()


def create_user(db: Session, user: schemas.UserCreate):
  db_user = models.User(
      email=user.email,
      username=user.username,
      full_name=user.full_name,
      hashed_password=user.hashed_password)
  db.add(db_user)
  db.commit()
  db.refresh(db_user)
  return db_user


def create_user_bbox(db: Session, bbox: schemas.BoundingBox, user_id: int):
  db_bbox = models.BoundingBox(**bbox.model_dump(), owner_id=user_id)
  db.add(db_bbox)
  db.commit()
  db.refresh(db_bbox)
  return db_bbox


def get_user_bboxes(db: Session, user_id: int) -> list[schemas.BoundingBox]:
  return (
    db.query(models.BoundingBox)
      .filter(models.BoundingBox.owner_id == user_id)
      .all()
  )


def get_all_bboxes(db: Session) -> list[models.BoundingBox]:
  return db.query(models.BoundingBox).all()


def set_bbox_update(db: Session, bbox_id: int, most_recent_data: str):
  db_cache = models.CacheBoundingBoxUpdate(
      bbox_id=bbox_id,
      most_recent_data=most_recent_data)
  db.add(db_cache)
  db.commit()
  db.refresh(db_cache)
  return db_cache


def get_last_cached_date(
    db: Session,
    bbox: models.BoundingBox,
    data_type: models.DataType) -> DateTime:
  res = (
    db.query(models.CacheBoundingBoxUpdate.most_recent_data)
      .filter(models.CacheBoundingBoxUpdate.bbox_id == bbox.id)
      .filter(models.CacheBoundingBoxUpdate.data_type_id == data_type.id)
      .one_or_none()
    )
  return res[0] if res else None

def set_last_cached_date(
    db: Session,
    bbox: models.BoundingBox,
    data_type: models.DataType,
    most_recent_data: DateTime):
  """ Upsert the last cached date for a bounding box and data type. """
  
  db_cache = (
    db.query(models.CacheBoundingBoxUpdate)
      .filter(models.CacheBoundingBoxUpdate.bbox_id == bbox.id)
      .filter(models.CacheBoundingBoxUpdate.data_type_id == data_type.id)
      .one_or_none()
  )
  if db_cache: # update
    db_cache.most_recent_data = most_recent_data
    db.commit()
    db.refresh(db_cache)
    return db_cache

  # create a new cache entry 
  db_cache = models.CacheBoundingBoxUpdate(
      bbox_id=bbox.id,
      data_type_id=data_type.id,
      most_recent_data=most_recent_data)
  db.add(db_cache)
  db.commit()
  db.refresh(db_cache)
  return db_cache

def get_data_types(db: Session):
  return db.query(models.DataType).all()