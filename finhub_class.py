#!/bin/env python3

# Modules
import os
import sys
import json
import logging
import datetime
import requests
from pprint import pprint

# Custom Modules
#sys.path.append(os.path.expanduser('~') + "/lazytrader")
sys.path.append(os.path.expanduser('~') + "/lazytrader-unreleased")

class FINHUB:
  # Variables
  file_data = None

  # Request Variables
  finhub_api = None
  base_url = "https://finnhub.io/api/v1"

  def __init__(self, file_data=None):
    if file_data:
      self.file_data = file_data

    # Set Variables
    try:
      self.finhub_api = self.file_data["finhub_api_key"]
    except TypeError:
      logging.error("Unable to locate Finhub.io API Key in config")

  # Determine the stock market is open
  def market_open(self):
    url = "%s/stock/market-status" % self.base_url
    url += "?exchange=US"
    url += "&token=%s" % self.finhub_api
    res = requests.get(url)
    
    if res.status_code == 200:
      res = res.json()

    if res["isOpen"]:
      return True
    else:
      return False

  # Get the news for a stock
  def get_news(self, symbol):
    cur_date = datetime.datetime.now()
    cur_date = cur_date.strftime("%Y-%m-%d")
    url = "%s/company-news" % self.base_url
    url += "?symbol=%s" % symbol
    url += "&from=%s" % cur_date
    url += "&to=%s" % cur_date
    url += "&token=%s" % self.finhub_api
    print(url)
    res = requests.get(url)

    if res.status_code == 200:
      res = res.json()
    pprint(res)

if __name__ == "__main__":
  user_config = os.path.expanduser('~') + "/user_config.json"
  import common_class

  # Initalize Common Class
  common_class = common_class.COMMON()

  # Initalize user config data
  file_data = common_class.get_user_data(user_config)

  a = FINHUB(file_data=file_data)
  print(a.market_open())

  print(a.get_news(symbol="AAPL"))
