from sqlalchemy import Column, ForeignKey, Integer, String, Float, Boolean
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


class BoundingBox(Base):
  __tablename__ = "bboxes"

  id = Column(Integer, primary_key=True, index=True)
  top_left_lat = Column(Float)
  top_left_lon = Column(Float)
  bottom_right_lat = Column(Float)
  bottom_right_lon = Column(Float)
  owner_id = Column(Integer, ForeignKey("users.id"))
  owner = relationship("User", back_populates="bboxes")