#!/bin/env python3

# Modules
import re
import os
import sys
import json
import pytz
import logging
import datetime
import requests
from pprint import pprint

# Custom Modules
#sys.path.append(os.path.expanduser('~') + "/lazytrader")
sys.path.append(os.path.expanduser('~') + "/lazytrader-unreleased")

class FINVIZ:
  # Variables
  url = "https://finviz.com/screener.ashx"
  headers = {
    "User-Agent": "curl/7.74.0"
  }

  def get_symbols(self, param=None):
    # Variables
    data = []
    stock_array = []

    if not param:
      return param

    # Get results from FinViz
    cur_session = requests.Session()
    logging.info("Sending request to FinViz stock screener")
    logging.debug("URL: %s" % self.url)
    logging.debug("Headers: %s" % self.headers)
    logging.debug("Parameters: %s" % param)
    res = cur_session.get(self.url, params=param, headers=self.headers)

    # Parse results
    for line in re.split("[<>]", res.text):
      if re.search("-- TS", line):
        stock_array = re.split("\n", line)
    
    for each_stock in stock_array:
      stock = re.search("^(\w+)|", each_stock)
      stock = stock.group(0).strip()
      if len(stock) == 0:
        continue
      data.append(stock)
    logging.info("Found %s number of stocks" % len(stock))
    logging.debug("Parsed FinViz stock data: %s" % data)
    return data

if __name__ == "__main__":
  # Variables
  log_level = logging.DEBUG
  #log_level = logging.ERROR
  param = "v=111&f=sh_avgvol_o2000%2Csh_price_1to10%2Cta_perf_52w10o%2Cta_rsi_ob60%2Cta_sma20_pa10%2Cta_sma200_pa10%2Cta_sma50_sb200&ft=3"
  param = "v=111&f=sh_avgvol_o2000,sh_price_1to10,ta_perf_52w10o,ta_sma20_pa10,ta_sma200_pa10,ta_sma50_sb200&ft=3"

  # Enable logging
  logging.basicConfig(level=log_level)

  # Initalize Class
  a = FINVIZ()

  # Get symbols from FinViz Parmeters
  a.get_symbols(param)
