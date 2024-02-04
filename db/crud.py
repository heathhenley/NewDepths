from sqlalchemy.orm import Session

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
