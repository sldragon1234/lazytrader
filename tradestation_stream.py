#!/bin/env python3

# Modules
import os
import sys
import json
import logging
import requests
from pprint import pprint

# Custom Modules
#sys.path.append(os.path.expanduser('~') + "/lazytrader")
sys.path.append(os.path.expanduser('~') + "/lazytrader-unreleased")

import common_class
import tradestation_class

if __name__ == "__main__":
  # Variables
  log_level = logging.ERROR
  #log_level = logging.INFO
  #log_level = logging.DEBUG
  log_format = "%(asctime)s: %(levelname)s: %(message)s - [%(filename)s: %(lineno)d]"
  broker = "tradestation"
  tradestation_auth_file = os.path.expanduser('~') + "/tradestation_auth"
  user_config = os.path.expanduser('~') + "/user_config.json"
  url = "https://api.tradestation.com/v3/marketdata/stream/quotes"
  headers = {}

  # Quote Variables
  quote = {}
  keywords_wanted = ["Bid", "Ask", "Last"]
  filename = os.path.expanduser('~') + "/lazytrader-unreleased/tradestation_quote"

  # Initalize Logging
  logging.basicConfig(level=log_level, format=log_format)

  # Initalize Classes
  common = common_class.COMMON()
  file_data = common.get_user_data(user_config)
  tradestation = tradestation_class.TRADESTATION_CLASS(file_data)

  # Get all the symbols to stream
  stock_list = list(file_data[broker]["stocks"].keys())
  url += "/%s" % ",".join(stock_list)

  while True:
    print("Restarting the Stream Loop: %s" % tradestation.get_date(raw_flag=False, hour_format=True))

    # Ensure we have working access token
    access_token = tradestation.handle_auth()

    # Create the header
    headers = {"Authorization": "Bearer %s" % access_token}

    # Ask broker for stream
    response = requests.request("GET", url, headers=headers, stream=True)

    # Parse stream for each line
    for line in response.iter_lines():
      if line:
        logging.debug(line)
        line = json.loads(line)
        if "Error" in list(line.keys()):
          pprint(line)
        try: 
          cur_symbol = line["Symbol"]
        except KeyError:
          continue

        if cur_symbol not in quote:
          quote[cur_symbol] = {}

        # Get only the information we want
        for each in keywords_wanted:
          try:
            quote[cur_symbol][each] = line[each]
          except KeyError:
            pass
      logging.info("Writing JSON Quote to file %s" % filename)
      logging.info(quote)
      common.write_json(quote, file=filename)
