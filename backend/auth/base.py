from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from db import crud
from settings import SECRET_KEY, ALGORITHM


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def verify_password(plain_password, hashed_password):
  return pwd_context.verify(plain_password, hashed_password)


def hash_password(password):
  return pwd_context.hash(password)


def authenticate_user(db: Session, email: str, password: str):
  user = crud.get_user_by_email(db, email)
  if not user:
    return False
  if not verify_password(password, user.hashed_password):
    return False
  return user


def create_access_token(data: dict, expires_delta: timedelta):
  to_encode = data.copy()
  expire = datetime.now(timezone.utc) + expires_delta
  to_encode.update({"exp": expire})
  encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
  return encoded_jwt


def strong_password(password: str):
  """ Check if the password is strong enough. """
  return len(password) >= 8
