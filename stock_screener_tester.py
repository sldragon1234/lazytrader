#!/bin/env python3

# Modules
import re
import os
import sys
import time
import json
import pytz
import logging
import requests
import datetime
import argparse
from pprint import pprint

# Custom Modules
sys.path.append(os.path.expanduser('~') + "/lazytrader")
import common_class
import finviz_class

if __name__ == "__main__":
  # Variables
  log_level = logging.ERROR
  #log_level = logging.INFO
  #log_level = logging.DEBUG
  log_format = "%(asctime)s: %(levelname)s: %(message)s - [%(filename)s: %(lineno)d]"
  cur_date = datetime.datetime.now()
  end_date = datetime.datetime.strptime("%s 15:00:00" % cur_date.strftime("%Y-%m-%d"), "%Y-%m-%d %H:%M:%S")
  cur_date = datetime.datetime.now()
  output_file = "Screener_Test.json"
  sleep_timer = 120

  # Email Variable
  subject = "Stock Screener Test Requests - %s " % cur_date.strftime("%Y-%m-%d")
  msg = ""
  email = None
  email_bypass = False

  # Config Variables
  data = {}
  delete_flag = True
  filename = None
  class_path = os.path.expanduser('~') + "/lazytrader-unreleased"
  user_config = os.path.expanduser('~') + "/lazytrader-unreleased/user_config.json"
  user_config = os.path.expanduser('~') + "/user_config.json"

  # Create the parser
  parser = argparse.ArgumentParser()

  # Add an argument
  parser.add_argument('-v', '--verbose', action='store_true', help="Verbose Logging")
  parser.add_argument('-d', '--debug', action='store_true', help="Debug Logging")
  parser.add_argument('-f', '--file', help="File to output data")
  parser.add_argument('-u', '--user_config', help="User JSON Config File")
  parser.add_argument('-e', '--email_address', help="Email Address")
  parser.add_argument('-b', '--email_bypass', action='store_true', help="Bypass send email")
  parser.add_argument('-D', '--no_delete', action='store_true', help="DO NOT Delete the old data")

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
  if args.email_address:
    email = args.email_address
  if args.email_bypass:
    email_bypass = True
  if args.no_delete:
    delete_flag = False

  # Initalize Logging
  if filename:
    logging.basicConfig(level=log_level, filename=filename, filemode='w', format=log_format)
  else:
    logging.basicConfig(level=log_level, format=log_format)

  # Initalize Common Class
  common_class = common_class.COMMON()
  finviz = finviz_class.FINVIZ()

  # Initalize user config data
  file_data = common_class.get_user_data(user_config)
  logging.debug("User Config Data from: %s" % user_config)
  logging.debug(file_data)

  # Initalize Broker from User Config
  for key in list(file_data.keys()):
    # Initalize Class
    try:
      logging.info("Loading %s class file" % key.lower())
      module = __import__("%s_class" % key.lower())
    except ModuleNotFoundError:
      continue
    for each in dir(module):
      if re.search(key, each.lower()):
        broker = getattr(module, each.upper())
        broker = broker(file_data)

  # Delete old contents from Screener Test Output
  if delete_flag:
    with open(output_file, "w") as h:
      json.dump({}, h)

  #
  # Main Loop
  #
  while True:
    cur_date = datetime.datetime.now()
    for screener_name, param in file_data[broker.broker]["screeners"].items():

      # Get Screener stocks
      stock_list = finviz.get_symbols(param)

      if len(stock_list) == 0:
        logging.error("No symbols found for %s" % screener_name)
        continue

      # Ensure we have working access token
      broker.access_token = broker.handle_auth()

      # Get Account Balance
      url = broker.base_url + "/marketdata/quotes/%s" % ",".join(stock_list)
      logging.debug("Send Broker %s" % url)
      res = requests.get(url, headers=broker.headers)
      status_code = res.status_code
      if status_code == 200:
        results = res.json()
      else:
        logging.error("Got the status code of %s" % status_code)
        logging.error(res.text)

      # Verify we have data
      if "Quotes" not in results:
        logging.error("Unable to find quotes for %s" % screener_name)

      # Get the current time
      cur_time = datetime.datetime.now().strftime("%H:%M:%S")

      # Create the output file is missing
      if not os.path.exists(output_file):
        with open(output_file, "w") as h:
          h.write("")
      
      # Get data from file
      with open(output_file, "r") as h:
        try:
          data = json.load(h)
        except json.decoder.JSONDecodeError:
          data = {}

      # Parse Market Data per Screener
      for each in results["Quotes"]:
        symbol = each["Symbol"]
        open_price = float(each["PreviousClose"])
        close_price = float(each["Close"])
        net_price = round(float(close_price - open_price), 2)
  
        if screener_name not in data:
          data[screener_name] = {}
        if symbol not in data[screener_name]:
          data[screener_name][symbol] = {}

        data[screener_name][symbol][cur_time] = {
          "Open_Price": open_price,
          "Close_Price": close_price,
          "Net_Price": net_price
        }

      # Write current data to file
      with open(output_file, "w") as h:
        json.dump(data, h)

    if cur_date > end_date:
      break
    time.sleep(sleep_timer)

  #
  # E-Mail Section
  #
  msg = "<table><tr>"
  msg += "<th>Screener</th>"
  msg += "<th>Symbol</th>"
  msg += "<th>Open Price</th>"
  msg += "<th>Close Price</th>"
  msg += "<th>Net Price</th>"
  msg += "</tr>"

  for name, cur_data in data.items():
    #msg += "<tr>"
    #msg += "<td>%s</td>" % name
    for symbol, each_data in cur_data.items():
      for cur_time, the_data in each_data.items():
        msg += "<tr>"
        msg += "<td>%s</td>" % name
        msg += "<td>%s</td>" % symbol
        msg += "<td>%s</td>" % data[name][symbol][cur_time]["Open_Price"]
        msg += "<td>%s</td>" % data[name][symbol][cur_time]["Close_Price"]
        msg += "<td>%s</td>" % data[name][symbol][cur_time]["Net_Price"]
        msg += "</tr>"
      msg += "<tr>"
      msg += "<td>------------------</td>"
      msg += "<td>------------------</td>"
      msg += "<td>------------------</td>"
      msg += "<td>------------------</td>"
      msg += "<td>------------------</td>"
      msg += "</tr>"

  msg += "</table><p>"

  common_class.send_email(msg, email, subject, email_bypass)
 
