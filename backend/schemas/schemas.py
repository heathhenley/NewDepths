from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
  username: str
  email: EmailStr
  full_name: str | None = None
  active: bool = True

  class Config:
    from_attributes = True

class UserCreate(UserBase):
  hashed_password: str

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
  username: str | None = None

class DataTypes(BaseModel):
  name: str
  description: str | None = None
  base_url: str

  class Config:
    from_attributes = True