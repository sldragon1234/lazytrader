#!/bin/env python3

# Modules
import re
import os
import sys
import json
import logging
import smtplib
import datetime
import argparse
from pprint import pprint
from email.message import EmailMessage
from email.headerregistry import Address
from email.utils import make_msgid

# Custom Modules
sys.path.append(os.path.expanduser('~') + "/lazytrader")
import common_class

if __name__ == "__main__":
  # Variables 
  log_level = logging.ERROR
  #log_level = logging.INFO
  symbol = []
  transactions = {}
  days_back_list = [0]
  cur_date = datetime.datetime.now()

  # Config Variables
  filename = None
  class_path = os.path.expanduser('~') + "/lazytrader-unreleased"
  user_config = os.path.expanduser('~') + "/lazytrader-unreleased/user_config.json"

  # Email Variable
  email_server = "localhost"
  subject = "LazyTrader Unreleased Summary Report - %s - Days Checked: " % cur_date.strftime("%Y-%m-%d")
  from_address = ""
  msg = ""
  email = None
  email_bypass = False  

  # Create the parser
  parser = argparse.ArgumentParser()

  # Add an argument
  parser.add_argument('-v', '--verbose', action='store_true', help="Verbose Logging")
  parser.add_argument('-d', '--debug', action='store_true', help="Debug Logging")
  parser.add_argument('-D', '--days', action='append', help="Days Back in Time")
  parser.add_argument('-s', '--symbol', action='append', help="Which symbol to stream")
  parser.add_argument('-e', '--email_address', help="Email Address")
  parser.add_argument('-b', '--email_bypass', action='store_true', help="Bypass send email")

  # Parse the argument
  args = parser.parse_args()

  if args.verbose:
    log_level = logging.INFO
  if args.debug:
    log_level = logging.DEBUG
  if args.days:
    days_back_list = args.days
  if args.symbol:
    symbol = args.symbol
  if args.email_bypass:
    email_bypass = True
  if args.email_address:
    email = args.email_address

  # Initalize Logging
  logging.basicConfig(level=log_level)

  logging.debug("User Args: %s" % args)

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
      logging.debug("Initalize %s class" % key.lower())
    except ModuleNotFoundError:
      continue
    for each in dir(module):
      if re.search(key, each.lower()):
        broker = getattr(module, each.upper())
        broker = broker(file_data)

  for days_back in days_back_list:
    logging.info("Starting Review")
    logging.info("%s days ago" % days_back)

    # Convert days back to int, user input is a string
    days_back = int(days_back)

    # The transactions for the amount of time
    sdate = (cur_date - datetime.timedelta(days=days_back))  
    start_date = sdate.strftime("%Y-%m-%d")
    end_date = (cur_date).strftime("%Y-%m-%d")

    logging.debug("Start Date: %s" % start_date)
    logging.debug("End Date: %s" % end_date)

    transactions = broker.get_transactions(days_back=days_back)
    logging.debug("Transaction from broker: %s" % transactions)

    # Accumulation Calculations
    for cur_symbol in transactions:
      logging.info("Reviewing %s" % cur_symbol)
      if len(transactions[cur_symbol]) == 0:
        logging.info("No data found for %s, skipping" % cur_symbol)
        continue
    
      # Output
      msg += "<table><tr>"
      msg += "<th>Description</th><th>Value</th>"
      msg += "</tr><tr>"
      msg += "<td>Symbol</td><td>%s</td>" % cur_symbol
      msg += "</tr><tr>"
      msg += "<td>Days Checked:</td><td>%s</td>" % days_back
      msg += "</tr><tr>"
      msg += "<td>Start Date:</td><td>%s</td>" % start_date
      msg += "</tr><tr>"
      msg += "<td>End Date:</td><td>%s</td>" % end_date
      msg += "</tr><tr>"
   
      for key, val in transactions[cur_symbol].items():
        msg += "<td>%s</td><td>%s</td>" % (key, val)
        msg += "</tr><tr>"
      msg += "</tr></table>"
      msg += "<hr><p>"
    
  use_msg = "<HTML><BODY>"
  use_msg += msg
  use_msg += "</BODY></HTML>"

  if email_bypass:
    logging.info("Bypass emailed, displaying to console")
    print(json.dumps(transactions, indent=2))
    sys.exit()

  # Update Subject with days
  subject += ", ".join(days_back_list)

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
