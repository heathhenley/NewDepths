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
  NOAA_NOS_SURVEY_URL = r"https://gis.ngdc.noaa.gov/arcgis/rest/services/web_mercator/nos_hydro_dynamic/MapServer/1/query"

  data_sources = [
    {
      "name": "multibeam",
      "base_url": NOAA_MULTIBEAM_URL,
      "description": "NOAA Multibeam Data"
    },
    {
      "name": "csb0",
      "base_url": NOAA_CSB_POINTS_URL,
      "description": "NOAA CSB Data (points)"
    },
    {
      "name": "nos_survey",
      "base_url": NOAA_NOS_SURVEY_URL,
      "description": "NOAA NOS Survey Data"
    }
  ]

  db = next(get_db())

  if not db:
    return 1

  for source in data_sources:
    res = db.query(models.DataType).filter_by(name=source["name"]).first()
    if not res:
      db.add(models.DataType(**source))
  db.commit()


if __name__ == "__main__":
  main()
