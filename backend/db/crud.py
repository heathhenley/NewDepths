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


def delete_user_bbox(db: Session, bbox_id: int, user_id: int):
  # delete a bbox, but only if it belongs to the user
  db_bbox = (
    db.query(models.BoundingBox)
      .filter(models.BoundingBox.id == bbox_id)
      .filter(models.BoundingBox.owner_id == user_id)
      .first()
  )
  if db_bbox:
    # get the cache entries for this bbox and delete them too
    db.query(models.CacheBoundingBoxUpdate).filter(
      models.CacheBoundingBoxUpdate.bbox_id == bbox_id).delete()
    # get the data orders for this bbox and delete them too
    db.query(models.DataOrder).filter(
      models.DataOrder.bbox_id == bbox_id).delete()
    db.delete(db_bbox)
    db.commit()
    return True
  return False
  

def get_all_bboxes(db: Session) -> list[models.BoundingBox]:
  return db.query(models.BoundingBox).all()


def get_bbox_by_id(db: Session, bbox_id: int) -> models.BoundingBox:
  return (
    db.query(models.BoundingBox)
      .filter(models.BoundingBox.id == bbox_id)
      .first()
  )


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


def create_data_order(
    db: Session,
    user_id: int,
    data_order: schemas.DataOrderCreate) -> models.DataOrder:
  db_order = models.DataOrder(
      noaa_ref_id=data_order.noaa_ref_id,
      check_status_url=data_order.check_status_url,
      order_date=data_order.order_date,
      bbox_id=data_order.bbox_id,
      user_id=user_id,
      data_type=data_order.data_type,
      last_status="Created")
  db.add(db_order)
  db.commit()
  db.refresh(db_order)
  return db_order


def get_data_order_by_id(db: Session, order_id: int) -> models.DataOrder:
  return (
    db.query(models.DataOrder)
    .filter(models.DataOrder.id == order_id)
    .first()
  )