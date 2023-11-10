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
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

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
  class_path = os.path.expanduser('~') + "/lazytrader"
  user_config = os.path.expanduser('~') + "/lazytrader/user_config.json"

  # Email Variable
  email_server = "localhost"
  subject = "LazyTrader Summary Report - %s - Days Checked: " % cur_date.strftime("%Y-%m-%d")
  from_address = "lazytrader@northpole.com"
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

  for days_back in days_back_list:
    # re-initalize Variables
    result = {}
    profit = 0
    total_order_time = 0.0
    total_trans_time = 0.0
    success_counter = 0
    fail_counter = 0
    old_order_counter = 0
    total_trans_counter = 0

    # Convert days back to int, user input is a string
    days_back = int(days_back)

    # The transactions for the amount of time
    sdate = (cur_date - datetime.timedelta(days=days_back))  
    start_date = sdate.strftime("%Y-%m-%d")
    end_date = (cur_date).strftime("%Y-%m-%d")

    transactions = broker.get_transactions(days_back=days_back)

    # Accumulation Calculations
    for cur_symbol in transactions:
      if len(transactions[cur_symbol]) == 0:
        profit = 0
        success_counter = 0
        old_order_counter = 0
        total_trans_time = 0
        total_order_time = 0
        total_trans_counter = 0
      else:  
        profit = round(float(transactions[cur_symbol]["profit"]), 2)
        success_counter = int(transactions[cur_symbol]["success_counter"])
        old_order_counter = int(transactions[cur_symbol]["old_order_counter"])
        total_trans_time = round(float(transactions[cur_symbol]["total_trans_time"]), 2)
        total_order_time = round(float(transactions[cur_symbol]["total_order_time"]), 2)
        total_trans_counter = int(transactions[cur_symbol]["total_trans_counter"])

      try:
        transactions[cur_symbol]["avg_trans_delay"] = round((total_trans_time / total_trans_counter) / 60, 2)
        transactions[cur_symbol]["avg_order_delay"] = round((total_order_time / total_trans_counter) / 60, 2)
      except ZeroDivisionError:
        logging.error("No Orders Found")
        transactions[cur_symbol]["avg_trans_delay"] = "N/A"
        transactions[cur_symbol]["avg_order_delay"] = "N/A"

      fail_counter = int(total_trans_counter - success_counter)
      try:
        transactions[cur_symbol]["perc_success"] = round((success_counter / total_trans_counter) * 100, 0)
      except ZeroDivisionError:
        logging.error("No Transactions Found")
        transactions[cur_symbol]["perc_success"] = "N/A"

      try:
        transactions[cur_symbol]["pos_holding_perc"] = round((old_order_counter / total_trans_counter) * 100, 0)
        transactions[cur_symbol]["profit"] = round(profit, 2)
      except ZeroDivisionError:
        logging.error("No Profit Found")
        transactions[cur_symbol]["profit"] = "N/A"
        transactions[cur_symbol]["pos_holding_perc"] = "N/A"
    
    # Output
    for cur_symbol in transactions:
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
      msg += "<td>Total Successful Transaction:</td><td>%s</td>" % transactions[cur_symbol]["success_counter"]
      msg += "</tr><tr>"
      msg += "<td>Total Failure Transaction:</td><td>%s</td>" % fail_counter
      msg += "</tr><tr>"
      msg += "<td>Total Opened Positions:</td><td>%s</td>" % transactions[cur_symbol]["old_order_counter"]

      msg += "</tr><tr>"
      msg += "<td>Avg Transaction Delay (minutes):</td><td>%s</td>" % transactions[cur_symbol]["avg_trans_delay"]
      msg += "</tr><tr>"
      msg += "<td>Holding Positions Perc:</td><td>%s</td>" % transactions[cur_symbol]["pos_holding_perc"]
      msg += "</tr><tr>"
      msg += "<td>Transaction Success Perc:</td><td>%s</td>" % transactions[cur_symbol]["perc_success"]
      msg += "</tr><tr>"
      try:
        msg += "<td>Profit:</td><td>%.2f</td>" % transactions[cur_symbol]["profit"]
      except TypeError:
        msg += "<td>Profit:</td><td>%s</td>" % transactions[cur_symbol]["profit"]
      msg += "</tr></table>"
      msg += "<hr><p>"
    
  use_msg = "<HTML><BODY>"
  use_msg += msg
  use_msg += "</BODY></HTML>"

  if email_bypass:
    print(msg)
  else:
    # Update Subject with days
    subject += ", ".join(days_back_list)

    # Generate Email Message
    email_msg = MIMEMultipart('alternative')
    email_msg['Subject'] = subject
    email_msg['From'] = from_address
    email_msg['To'] = email
    use_msg = MIMEText(use_msg, 'html')
    email_msg.attach(use_msg)

    # Send Email
    if email:
      logging.info("Sending Email to %s" % email)
      logging.debug("To: %s" % email)
      logging.debug("From: %s" % from_address)
      logging.debug("Subject: %s" % subject)
      logging.debug("Message: %s" %  email_msg.as_string())
      s = smtplib.SMTP(email_server)
      s.sendmail(from_address, email, email_msg.as_string())
      s.quit()
    else:
      logging.error("No Email Address Provided")
