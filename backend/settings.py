import os

from dotenv import load_dotenv


load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))

if SECRET_KEY is None or ALGORITHM is None:
  raise Exception("SECRET_KEY and ALGORITHM must be set in .env file")