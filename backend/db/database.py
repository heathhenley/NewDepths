from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import os

load_dotenv()
SQLALCHEMY_DATABASE_URL = os.getenv(
  "DB_CONNECT_STR",
  "postgresql://postgres:postgres@localhost:5432/test_db")

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
# create all tables
Base.metadata.create_all(bind=engine)