import os

from dotenv import load_dotenv


load_dotenv(os.getenv("ENV_FILE", ".env"))
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
SQLALCHEMY_DATABASE_URL = os.getenv(
  "DB_CONNECT_STR",
  "postgresql://postgres:postgres@localhost:5432/test_db")
RESEND_KEY = os.getenv("RESEND_KEY")


if SECRET_KEY is None or ALGORITHM is None:
  raise Exception("SECRET_KEY and ALGORITHM must be set in .env file")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

DEFAULT_RATE_LIMIT = f"{os.getenv('RATE_LIMIT_PER_MINUTE', 60)}/minute"
