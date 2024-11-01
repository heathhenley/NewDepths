from sqlalchemy.orm import Session

from fastapi import Depends, HTTPException, Request, status
from jose import jwt

from db.models import User
from db import crud

from dependencies.db import get_db

from settings import SECRET_KEY, ALGORITHM

# Get the user from the JWT - helper - sometimes we don't want to redirect,
# just check if the user is logged in or not
def get_user_or_none(token: str, db: Session) -> User:
  payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
  email = payload.get("sub")
  if email is None or not (user := crud.get_user_by_email(db, email)):
    return None
  return user


# Logged in user dependency
def get_user_or_redirect(
    request: Request,
    url: str = "/login",
    db: Session = Depends(get_db)) -> User:
  """ Get the user from the JWT in the http only cookie

  If the user is not found, redirect to the url parameter. 
  """

  if not (token := request.cookies.get("token", None)):
    raise HTTPException(
      status_code=status.HTTP_307_TEMPORARY_REDIRECT,
      detail="Redirecting to login - not authenticated",
      headers={"Location": url})

  try:
    if not (user := get_user_or_none(token, db)):
      raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        detail="Redirecting to login - not authenticated",
        headers={"Location": url})
  except HTTPException:
    raise HTTPException(
      status_code=status.HTTP_307_TEMPORARY_REDIRECT,
      detail="Redirecting to login - not authenticated",
      headers={"Location": url})
  return user
