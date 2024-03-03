from db.database import SessionLocal
from db import models


def get_db():
  db = SessionLocal()
  try:
    yield db
  finally:
    db.close()


def main():
  NOAA_MULTIBEAM_URL = r"https://gis.ngdc.noaa.gov/arcgis/rest/services/web_mercator/multibeam_dynamic/MapServer/0/query"
  NOAA_CSB_POINTS_URL = r"https://gis.ngdc.noaa.gov/arcgis/rest/services/csb/MapServer/0/query"

  db = next(get_db())

  if not db:
    return 1

  # add types to the db
  res = db.query(models.DataType).filter_by(name="multibeam").first()
  if not res:
    db.add(models.DataType(name="multibeam", base_url=NOAA_MULTIBEAM_URL,
      description="NOAA Multibeam Data"
    ))
  db.commit()

  res = db.query(models.DataType).filter_by(name="csb0").first()
  if not res:
    db.add(
      models.DataType(
        name="csb0",
        base_url=NOAA_CSB_POINTS_URL,
        description="NOAA CSB Data (points)"
    ))
  db.commit()

if __name__ == "__main__":
  main()
