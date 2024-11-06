from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_remote_address_xreal(request: Request):
  # This is a custom function to get the real IP address based on the header
  # that railway sets
  #print(request.headers.get("x-real-ip"))
  return request.headers.get("x-real-ip") or get_remote_address(request)


# Rate limiting
limiter = Limiter(
  key_func=get_remote_address_xreal,
  default_limits=["10/minute"],
  application_limits=["30/minute"],
  
)

