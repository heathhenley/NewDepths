import datetime
from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
  email: EmailStr
  full_name: str | None = None
  active: bool = True

  class Config:
    from_attributes = True


class UserCreate(UserBase):
  google_sub: str | None = None
  hashed_password: str | None = None

  def validate_user(self):
    if not self.hashed_password and not self.google_sub:
      raise ValueError(
        "User must have either a hashed password or a google sub")
  class Config:
    from_attributes = True


class UserFromForm(UserBase):
  password: str
  password_confirm: str

  class Config:
    from_attributes = True


class BoundingBox(BaseModel):
  top_left_lat: float
  top_left_lon: float
  bottom_right_lat: float
  bottom_right_lon: float

  class Config:
    from_attributes = True


class User(UserBase):
  bboxes: list[BoundingBox] = []

  class Config:
    from_attributes = True


class Token(BaseModel):
  access_token: str
  token_type: str


class TokenData(BaseModel):
  email: EmailStr | None = None


class DataTypes(BaseModel):
  name: str
  description: str | None = None
  base_url: str

  class Config:
    from_attributes = True


class DataOrderCreate(BaseModel):
  noaa_ref_id: str
  order_date: datetime.datetime
  check_status_url: str | None = None
  bbox_id: int
  data_type: str
  last_status: str | None = None
  output_location: str | None = None

  class Config:
    from_attributes = True