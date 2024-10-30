import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse


rick_roll_router = APIRouter()


bot_words = [
  "wp-admin", "wp-login", "wp-content", "wp-includes", "wp-json", ".php",
  ".env", 
]


# a catch all route, redirect to rickroll if contains any of the common bot
# words - NOTE: This needs to be the last route in the file
@rick_roll_router.get("/{catchall:path}", include_in_schema=False)
def catchall(request: Request, catchall: str):
  logging.info(f"catchall redirect: {catchall}")
  if any([x in catchall for x in bot_words]):
    return RedirectResponse("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
  raise HTTPException(
    status_code=404,
    detail="Page not found"
  )
