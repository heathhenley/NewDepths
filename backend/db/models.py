from sqlalchemy import (
  Column, ForeignKey, Integer, String, Float, Boolean, DateTime
)
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
  __tablename__ = "users"

  id = Column(Integer, primary_key=True, index=True)
  email = Column(String, unique=True, index=True)
  username = Column(String, unique=True, index=True)
  full_name = Column(String)
  active = Column(Boolean, default=True)
  hashed_password = Column(String)
  bboxes = relationship("BoundingBox", back_populates="owner")
  data_orders = relationship("DataOrder", back_populates="user")


class BoundingBox(Base):
  __tablename__ = "bboxes"

  id = Column(Integer, primary_key=True, index=True)
  top_left_lat = Column(Float)
  top_left_lon = Column(Float)
  bottom_right_lat = Column(Float)
  bottom_right_lon = Column(Float)
  owner = relationship("User", back_populates="bboxes")
  owner_id = Column(Integer, ForeignKey("users.id"))


class DataType(Base):
  __tablename__ = "data_types"
  id = Column(Integer, primary_key=True, index=True)
  name = Column(String, unique=True, index=True)
  description = Column(String, nullable=True)
  base_url = Column(String, nullable=False)


class CacheBoundingBoxUpdate(Base):

  __tablename__ = "cache_bbox_updates"

  id = Column(Integer, primary_key=True, index=True)
  most_recent_data = Column(DateTime, nullable=True)
  bbox_id = Column(Integer, ForeignKey("bboxes.id"))
  data_type_id = Column(Integer, ForeignKey("data_types.id"))


class DataOrder(Base):

  __tablename__ = "data_orders"

  id = Column(Integer, primary_key=True, index=True)
  noaa_ref_id = Column(String, unique=True, index=True)
  order_date = Column(DateTime, nullable=False)
  check_status_url = Column(String, nullable=True)
  bbox_id = Column(Integer, ForeignKey("bboxes.id"))
  data_type = Column(String, nullable=False)
  user = relationship("User", back_populates="data_orders")
  user_id = Column(Integer, ForeignKey("users.id"))
  last_status = Column(String, nullable=True)
