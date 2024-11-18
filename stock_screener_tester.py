#!/bin/env python3

# Modules
import re
import os
import sys
import time
import json
import pytz
import logging
import smtplib
import requests
import datetime
import argparse
from pprint import pprint
from email.message import EmailMessage
from email.headerregistry import Address
from email.utils import make_msgid

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

  # Email Variable
  email_server = "localhost"
  subject = "Stock Screener Test Requests - %s " % cur_date.strftime("%Y-%m-%d")
  from_address = ""
  msg = ""
  email = None
  email_bypass = False

  # Config Variables
  data = {}
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

    # Parse Market Data per Screener
    for each in results["Quotes"]:
      symbol = each["Symbol"]
      open_price = float(each["PreviousClose"])
      close_price = float(each["Close"])
      net_price = round(float(close_price - open_price), 2)

      if screener_name not in data:
        data[screener_name] = {}

      data[screener_name][symbol] = {
        "Open_Price": open_price,
        "Close_Price": close_price,
        "Net_Price": net_price
      }

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
    msg += "<tr>"
    msg += "<td>%s</td>" % name
    msg += "<td>%s</td>" % symbol
    msg += "<td>%s</td>" % data[name][symbol]["Open_Price"]
    msg += "<td>%s</td>" % data[name][symbol]["Close_Price"]
    msg += "<td>%s</td>" % data[name][symbol]["Net_Price"]
  msg += "</tr>"
  msg += "<td>------------------</td>"
  msg += "<td>------------------</td>"
  msg += "<td>------------------</td>"
  msg += "<td>------------------</td>"
  msg += "<td>------------------</td>"
  msg += "</tr>"

msg += "</table><p>"

if email_bypass:
  print(msg) 
  sys.exit()

use_msg = "<HTML><BODY>"
use_msg += "<pre>%s</pre>" % msg
use_msg += "</BODY></HTML>"

# Generate Email Message
try:
  raw_email = email.split('@')
  user = raw_email[0]
  domain = raw_email[1]
except:
  logging.error("Email provide is malformed: %s" % email)
  sys.exit()

msg = EmailMessage()
msg['Subject'] = subject
msg['From'] = Address(email, user, domain)
msg['To'] = Address(email, user, domain)
msg.set_content("Yo")

# Add the html version.  This converts the message into a multipart/alternative
# container, with the original text message as the first part and the new html
# message as the second part.
asparagus_cid = make_msgid()
msg.add_alternative(use_msg.format(asparagus_cid=asparagus_cid[1:-1]), subtype='html')
# note that we needed to peel the <> off the msgid for use in the html.

# Send Email
if email:
  logging.debug("Sending email to %s" % msg['To'])
  logging.debug("To: %s" % msg['To'])
  logging.debug("From: %s" % msg['From'])
  logging.debug("Subject: %s" % msg['Subject'])
  logging.debug("Body: %s" % msg.as_string)

  # Send the message via local SMTP server.
  with smtplib.SMTP('localhost') as s:
    s.send_message(msg)
    s.quit()
    logging.info("Email Sent")
else:
  logging.error("No Email Address Provided")
 
