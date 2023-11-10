#!/bin/env python3

# Modules
import re
import os
import sys
import time
import pytz
import logging
import datetime
import argparse
from pprint import pprint

# Custom Modules
sys.path.append(os.path.expanduser('~') + "/lazytrader")
import common_class

if __name__ == "__main__":
  # Variables
  sleep_timer = 30
  cancel_order_in_minutes = 10
  log_level = logging.ERROR
  #log_level = logging.INFO
  #log_level = logging.DEBUG
  log_format = "%(asctime)s: %(levelname)s: %(message)s - [%(filename)s: %(lineno)d]"

  # Config Variables
  filename = None
  class_path = os.path.expanduser('~') + "/lazytrader"
  user_config = os.path.expanduser('~') + "/lazytrader/user_config.json"

  # Trade Varables
  market_counter = 0
  current_spend = 0
 
  # Create the parser
  parser = argparse.ArgumentParser()

  # Add an argument
  parser.add_argument('-v', '--verbose', action='store_true', help="Verbose Logging")
  parser.add_argument('-d', '--debug', action='store_true', help="Debug Logging")
  parser.add_argument('-f', '--file', help="File to output data")
  parser.add_argument('-u', '--user_config', help="User JSON Config File")

  # Parse the argument
  args = parser.parse_args()

  if args.verbose:
    log_level = logging.INFO
  if args.debug:
    log_level = logging.DEBUG
  if args.file:
    filename = args.file
  if args.user_config:
    user_config = args.user_config

  # Initalize Logging
  if filename:
    logging.basicConfig(level=log_level, filename=filename, filemode='w', format=log_format)
  else:
    logging.basicConfig(level=log_level, format=log_format)

  # Initalize Common Class
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

  # Get total daily trading amount
  spend_per_day = broker.get_spending_amount()

  # Set Variables
  cancel_order_in_minutes = file_data[broker.broker]["cancel_order_in_minutes"]
  delay_market_open = file_data["delay_market_open"]
  sleep_timer = file_data["sleep_timer"]
  stocks = file_data[broker.broker]["stocks"]
  symbol_list = list(stocks.keys())

  #
  # Main Loop
  #
  while True:

    # Verify Market is Open
    try:
      if not broker.market_open(delay_market_open):
        market_counter = 0
        current_spend = 0
        time.sleep(sleep_timer)
        continue
    except:
      logging.error("Connection to server failed")
      time.sleep(sleep_timer)
      continue

    if market_counter == 0:
      logging.info("Market is open")

    # Place Buy Order
    broker.place_orders()

    # Cancel Old Orders
    broker.cancel_orders()

    # Wait until the next cycle
    market_counter += 1
    time.sleep(sleep_timer)

