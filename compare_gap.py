#!/bin/env python3

# Modules
import re
import os
import sys
import json
import logging
import datetime
import argparse
from pprint import pprint

# Custom Modules
sys.path.append(os.path.expanduser('~') + "/lazytrader")
import common_class

if __name__ == "__main__":
  # Variables 
  log_level = logging.ERROR
  #log_level = logging.INFO
  symbol_list = []
  days_back = 0
  cur_date = datetime.datetime.now()

  # Config Variables
  filename = None
  class_path = os.path.expanduser('~') + "/lazytrader"
  user_config = os.path.expanduser('~') + "/lazytrader/user_config.json"

  # Create the parser
  parser = argparse.ArgumentParser()

  # Add an argument
  parser.add_argument('-v', '--verbose', action='store_true', help="Verbose Logging")
  parser.add_argument('-d', '--debug', action='store_true', help="Debug Logging")
  parser.add_argument('-D', '--days', required=True, help="Days Back in Time")
  parser.add_argument('-s', '--symbol', required=True, action='append', help="Stock Symbol(s)")

  # Parse the argument
  args = parser.parse_args()

  if args.verbose:
    log_level = logging.INFO
  if args.debug:
    log_level = logging.DEBUG
  if args.days:
    days_back = args.days
  if args.symbol:
    symbol_list = args.symbol

  # Initalize Logging
  logging.basicConfig(level=log_level)

  # Initalize common class
  common_class = common_class.COMMON()

  # Initalize user config data
  file_data = common_class.get_user_data(user_config)
  logging.debug("User Config Data from: %s" % user_config)
  logging.debug(file_data)

  # Initalize Broker from User Config
  for key in list(file_data.keys()):
    # Initalize Class
    try:
      module = __import__("%s_class" % key.lower())
    except ModuleNotFoundError:
      continue
    for each in dir(module):
      if re.search(key, each.lower()):
        broker = getattr(module, each.upper())
        broker = broker(file_data)

  for symbol in symbol_list:
    results = broker.get_stock_price_gap(symbol, days_back=days_back)
    print(symbol)
    print("Price: Transaction Count")
    pprint(results)
    print("----------------------------------------------")

