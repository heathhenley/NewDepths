from dataclasses import dataclass, field
from datetime import datetime
import logging
import urllib.parse

import requests

from db import models


def build_url(base_url: str, query_params: dict) -> str:
  """ Build a url from a base url and a dictionary of query parameters. """
  return f"{base_url}?{urllib.parse.urlencode(query_params)}"


def bbox_to_envelope(bbox: models.BoundingBox) -> str:
  """ Convert a bbox to a string in the correct esri format for 'envelope'."""
  xmin = min(bbox.top_left_lon, bbox.bottom_right_lon)
  xmax = max(bbox.top_left_lon, bbox.bottom_right_lon)
  ymin = min(bbox.top_left_lat, bbox.bottom_right_lat)
  ymax = max(bbox.top_left_lat, bbox.bottom_right_lat)
  return f"{xmin},{ymin},{xmax},{ymax}"


@dataclass
class SurveyDataPoint:
  """ A generalized class to hold survey data of any type."""
  time: datetime | None = None
  download_url: str | None = None
  platform: str | None = None
  name: str | None = None

@dataclass
class SurveyDataList:
  """ A generalized class to hold a list of SurveyDataPoints."""
  data: list[SurveyDataPoint] = field(default_factory=list)
  json_url: str | None = None
  description: str | None = None
  bbox: models.BoundingBox | None = None

  def add(self, time=None, download_url=None, platform=None, name=None):
    self.data.append(SurveyDataPoint(time, download_url, platform, name))
  
  def get_latest_datetime(self) -> datetime | None:
    if not self.data:
      return None
    return self.data[0].time


class DataFetcherBase:
  """ Base class for fetching data from the NOAA API.
  
  Subclasses should implement the get_data method to return a SurveyDataList,
  mapping any data source specific fields to the SurveyDataPoint fields where
  appropriate.
  """
  def __init__(self, base_url: str, data_type: str, description: str):
    self.base_url = base_url
    self.data_type = data_type
    self.description = description
  
  def get_data(
      self, bbox: models.BoundingBox, since: datetime | None) -> SurveyDataList:
    raise NotImplementedError


class MultibeamDataFetcher(DataFetcherBase):
  """ Fetch from the NOAA API and map it to a common response format.
  
  Just going to make it easier to use in the rest of the app."""

  def _get_query_params(self, bbox: models.BoundingBox, since: datetime | None):
    """ Speficic query params for multibeam data. """
    return {
      'f': 'json',
      'where': 'ENTERED_DATE IS NOT NULL',
      'geometry': bbox_to_envelope(bbox),
      'geometryType': 'esriGeometryEnvelope',
      'inSR': 4326,
      'spatialRel': 'esriSpatialRelIntersects',
      'outFields': 'SURVEY_ID,PLATFORM,DOWNLOAD_URL,START_TIME,END_TIME,ENTERED_DATE',
      'returnGeometry': False,
      'orderByFields': 'ENTERED_DATE DESC'
    }
  
  def _get_data_from_noaa_api(
    self, url: str, query_params: dict, bbox: models.BoundingBox) -> str | None:
    """ Make the actual request to the NOAA API. """
    try:
      res = requests.get(url, params=query_params, timeout=60)
      if res.status_code != 200:
        raise Exception(f"Bad response from NOAA: {res.status_code}")
    except Exception as e:
      logging.error(f"Error getting data for bbox {bbox.id}: {e}")
      return None
    return res.json()

  def _map_api_response_to_data_list(
      self,
      bbox: models.BoundingBox,
      query_params: dict,
      surveys: list[dict]) -> SurveyDataList:
    """ Map the response from the NOAA API to a SurveyDataList. """
    data = SurveyDataList(
      json_url=build_url(self.base_url, query_params),
      description=self.description,
      bbox=bbox
    )
    for survey in surveys:
      data.add(
        time=datetime.fromtimestamp(
          survey["attributes"]["ENTERED_DATE"] / 1000.0),
        download_url=survey["attributes"]["DOWNLOAD_URL"],
        platform=survey["attributes"]["PLATFORM"],
      )
    return data
 
  def get_data(
      self,
      bbox: models.BoundingBox,
      since: datetime | None) -> SurveyDataList | None:
    """ Fetch multibeam data from the NOAA API. """

    query_params = self._get_query_params(bbox, since)
    url = self.base_url

    if not (new_data := self._get_data_from_noaa_api(url, query_params, bbox)):
      return None
    
    if "error" in new_data:
      logging.error(f"Error in multibeam bb:{bbox.id}: {new_data['error']}")
      return None
    
    if not (surveys := new_data['features']):
      logging.info(f"No new data for bbox {bbox.id}")
      return None
  
    # we have data, need to map it to a SurveyDataList
    return self._map_api_response_to_data_list(bbox, query_params, surveys)


class CSBDataFetcher(DataFetcherBase):
  """ Fetch from the NOAA API and map it to a common response format.
  
  Just going to make it easier to use in the rest of the app."""

  def _get_query_params(self, bbox: models.BoundingBox, since: datetime | None):
    """ Speficic query params for csb data. """
    return {
      'f': 'json',
      'where': 'ARRIVAL_DATE IS NOT NULL',
      'geometry': bbox_to_envelope(bbox),
      'geometryType': 'esriGeometryEnvelope',
      'inSR': 4326,
      'spatialRel': 'esriSpatialRelIntersects',
      'outFields': 'NAME,PLATFORM,ARRIVAL_DATE,START_DATE,YEAR',
      'returnGeometry': False,
      'orderByFields': 'ARRIVAL_DATE DESC'
    }

  
  def _get_data_from_noaa_api(
    self, url: str, query_params: dict, bbox: models.BoundingBox) -> str | None:
    """ Make the actual request to the NOAA API. """
    try:
      res = requests.get(url, params=query_params, timeout=5)
      if res.status_code != 200:
        raise Exception(f"Bad response from NOAA: {res.status_code}")
    except Exception as e:
      logging.error(f"Error getting data for bbox {bbox.id}: {e}")
      return None
    return res.json()

  def _map_api_response_to_data_list(
      self,
      bbox: models.BoundingBox,
      query_params: dict,
      surveys: list[dict]) -> SurveyDataList:
    """ Map the response from the NOAA API to a SurveyDataList. """
    data = SurveyDataList(
      json_url=build_url(self.base_url, query_params),
      description=self.description,
      bbox=bbox
    )
    for survey in surveys:
      data.add(
        time=datetime.fromtimestamp(
          survey["attributes"]["ARRIVAL_DATE"] / 1000.0),
        platform=survey["attributes"]["PLATFORM"],
        name=survey["attributes"]["NAME"]
      )
    return data
 
  def get_data(
      self,
      bbox: models.BoundingBox,
      since: datetime | None) -> SurveyDataList | None:
    """ Fetch data from the NOAA API. """

    query_params = self._get_query_params(bbox, since)
    url = self.base_url

    if not (new_data := self._get_data_from_noaa_api(url, query_params, bbox)):
      return None
    
    if "error" in new_data:
      logging.error(f"Error in bb:{bbox.id}: {new_data['error']}")
      return None
    
    if not (surveys := new_data['features']):
      logging.info(f"No new data for bbox {bbox.id}")
      return None
  
    # we have data, need to map it to a SurveyDataList
    return self._map_api_response_to_data_list(bbox, query_params, surveys)


def data_fetcher_factory(data_type: models.DataType) -> DataFetcherBase:
  """ Factory function to return the correct DataFetcher for a DataType."""
  map_to_fetcher = {
    "multibeam": MultibeamDataFetcher,
    "csb0": CSBDataFetcher,
    "csb1": CSBDataFetcher,
  }
  return map_to_fetcher[data_type.name](
    data_type.base_url, data_type.name, data_type.description)
