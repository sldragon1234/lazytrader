#!/bin/env python3

# Modules
import re
import os
import sys
import time
import uuid
import pytz
import json
import logging
import requests
import datetime
from pprint import pprint

# Custom Modules
#sys.path.append(os.path.expanduser('~') + "/lazytrader")
sys.path.append(os.path.expanduser('~') + "/lazytrader-unreleased")

import common_class
import finhub_class

class TRADESTATION_CLASS:
  # Variables
  file_data = os.path.expanduser('~') + "/user_config.json"
  broker = "tradestation"
  max_login = 5
  auth_key_list = ["expires_date", "access_token", "refresh_token", "expires_in"]
  inital_load_flag = False
  unique_token = uuid.uuid4()

  # Request Variables
  headers = {"content-type": "application/x-www-form-urlencoded"}
  loopback = "http://localhost"
  base_url = "https://api.tradestation.com/v3"
  access_token = None

  # Config Variables
  access_token = None
  account_id = None
  account_secret = None
  account_type = None
  spend_per_day = None
  tradestation_auth_file = os.path.expanduser('~') + "/tradestation_auth"
  filename_quote = os.path.expanduser('~') + "/lazytrader-unreleased/tradestation_quote"

  # Trade Variables
  orders = None
  quote = {}
  current_spend = 0
  status_list = ["OPN", "Open", "ACK"]

  def __init__(self, file_data=None):
    if file_data:
      self.file_data = file_data

    # Set Variables
    logging.debug(self.file_data)
    self.access_token = self.file_data[self.broker]["access_token"]
    self.account_id = self.file_data[self.broker]["account_id"]
    self.client_id = self.file_data[self.broker]["client_id"]
    self.client_secret = self.file_data[self.broker]["client_secret"]
    self.account_type = self.file_data[self.broker]["account_type"]
    self.cancel_order_in_minutes = self.file_data[self.broker]["cancel_order_in_minutes"]
    self.stocks = self.file_data[self.broker]["stocks"]
    self.stock_list = list(self.stocks.keys())

    # Set Base URL
    if self.file_data[self.broker]["sandbox"] == True:
      self.base_url = self.sandbox_base_url
    logging.debug("Broker Base URL: %s" % self.base_url)

    # Set the headers
    self.headers["Authorization"] = "Bearer %s" % self.access_token

    # Get the amount to spend
    self.spend_per_day = self.get_spending_amount()
    logging.info("The total amount to spend today: %s" % self.spend_per_day)
    logging.info("List of stocks to trade: %s" % ", ".join(self.stock_list))
    logging.info("Transaction waiting longer then %s minutes will be canceled" % self.cancel_order_in_minutes)

    # Ensure we have working access token
    self.access_token = self.handle_auth()

  # Handle all aspects for authenticating with broker 
  def handle_auth(self, count=0):
    auth_keys = []

    if count >= self.max_login:
      logging.error("Authorization against broker %s API failed" % self.broker)
      sys.exit()

    # Initalize Classes
    if not self.inital_load_flag:
      # Initalize Classes
      self.finhub = finhub_class.FINHUB(file_data=self.file_data)
      self.common = common_class.COMMON()
      self.inital_load_flag = True

    cur_date = self.get_date()
    try:
      auth_data = self.common.read_json(file=self.tradestation_auth_file)
      auth_keys = list(auth_data.keys())
    except FileNotFoundError:
      pass

    # Verify we have auth code
    if "auth_code" not in auth_keys:
      self.authorize_user()
      count += 1
      return self.handle_auth(count=count)

    # Verify we have the remaining auth information
    for each_key in self.auth_key_list:    
      if each_key not in auth_keys:
        self.get_tokens(auth_code=auth_data["auth_code"])
        count += 1
        return self.handle_auth(count=count)

    # Check if we are over the expired date
    use_exp_date = auth_data["expires_date"].strip().replace(" ", "T")
    exp_date = self.get_date(specific_date=use_exp_date)
    if exp_date > cur_date:
      # Set the headers
      self.headers["Authorization"] = "Bearer %s" % auth_data["access_token"]
      return auth_data["access_token"]
    else:
      self.refresh_the_tokens()
      count += 1
      return self.handle_auth(count=count)

  # Prompt the user to login and get the auth code
  def authorize_user(self):
    url = "https://signin.tradestation.com/authorize"
    url += "?response_type=code"
    url += "&client_id=%s" % self.client_id
    url += "&redirect_uri=%s" % self.loopback
    url += "&audience=https://api.tradestation.com"
    url += "&state=%s" % self.unique_token
    url += "&scope=offline_access MarketData ReadAccount Trade"
    print(url)

    auth_code = input("Authorization Code: ")
    if len(auth_code) > 0 and re.search("[0-9a-zA-Z]+", auth_code):
      data = {"auth_code": auth_code}
      self.common.write_json(data, file=self.tradestation_auth_file)
      logging.info("Got Auth Code")
    else:
      print("Auth Code Validation Failed")
      sys.exit()

  # Connect to the broker to get auth tokens 
  def get_tokens(self, auth_code=None):
    # Variables
    url = "https://signin.tradestation.com/oauth/token"
    body = {
      "grant_type": "authorization_code",
      "client_id": self.client_id,
      "client_secret": self.client_secret,
      "code": auth_code,
      "redirect_uri": self.loopback
    }

    # Get the auth token from broker
    res = requests.post(url, data=body, headers=self.headers)
    if res.status_code != 200:
      logging.error("Failed to get tokens from %s broker" % self.broker)
      logging.error(res.text)
      sys.exit()
    
    # Results from the broker
    data = res.json()

    # Read the auth file
    auth_data = self.common.read_json(file=self.tradestation_auth_file)
    
    # Set broker data
    for key, val in data.items():
      auth_data[key] = val

    # Set the expired date for the tokens
    cur_date =  self.get_date()
    new_exp_time = int(auth_data["expires_in"]) - 120
    cur_date = cur_date + datetime.timedelta(seconds=new_exp_time)
    exp_date = self.get_date(specific_date=cur_date, raw_flag=False, hour_format=True, timezone_format=True)
    auth_data["expires_date"] = exp_date

    self.common.write_json(auth_data, file=self.tradestation_auth_file)
    logging.info("Got Auth Tokens")

  # Connect to the broker to refresh the auth tokens
  def refresh_the_tokens(self):
    # Read the broker auth file
    auth_data = self.common.read_json(file=self.tradestation_auth_file)

    # Variables
    url = "https://signin.tradestation.com/oauth/token"
    body = {
      "grant_type": "refresh_token",
      "client_id": self.client_id,
      "client_secret": self.client_secret,
      "refresh_token": auth_data["refresh_token"]
    }

    # Send request to the broker
    res = requests.post(url, data=body, headers=self.headers)
    if res.status_code != 200:
      logging.error("Refresh failed to get tokens from %s broker" % self.broker)
      logging.error(res.text)
      sys.exit()

    # Results from the broker
    data = res.json()

    # Read the auth file
    auth_data = self.common.read_json(file=self.tradestation_auth_file)

    # Set broker data
    for key, val in data.items():
      auth_data[key] = val

    # Set the expired date for the tokens
    cur_date =  self.get_date()
    cur_date = cur_date + datetime.timedelta(seconds=(int(auth_data["expires_in"] - 120)))
    exp_date = self.get_date(specific_date=cur_date, raw_flag=False, hour_format=True, timezone_format=True)
    auth_data["expires_date"] = exp_date

    self.common.write_json(auth_data, file=self.tradestation_auth_file)
    logging.info("Refeshed Auth Tokens")

  # Need to revoke tokens to force a full login again
  def revoke_tokens(self, login_again=True):
    # Read the broker auth file
    auth_data = self.common.read_json(file=self.tradestation_auth_file)

    # Variables
    url = "https://signin.tradestation.com/oauth/revoke"
    body = {
      "client_id": self.client_id,
      "client_secret": self.client_secret,
      "refresh_token": auth_data["refresh_token"]
    }

    # Send request to broker
    res = requests.post(url, data=body, headers={content-type: application/json})
    if res.status_code != 200:
      logging.error("Failed to revoke auth tokens for %s broker" % self.broker)
      logging.error(res.text)

    # Write a blank JSON record
    self.common.write_json({}, file=self.tradestation_auth_file)

    # Start the login process again from stratch
    if login_again:
      self.handle_auth()

  # Logic to place an order
  def place_orders(self):
    logging.info("Begin Place Order Check")
    # Ensure we have working access token
    self.access_token = self.handle_auth()

    # Get the current quote
    quote = self.get_quote()

    for symbol in self.stock_list:
      results = {}
      res = self.get_open_orders_by_symbol(symbol)
      if symbol in list(res.keys()):
        logging.debug("Found an open postition for %s, Skipping" % symbol)
        continue

      qty = int(self.stocks[symbol]["qty"])
      try:
        buy_price = round(float(self.quote[symbol]["Bid"]),2)
      except KeyError:
        logging.error("Quote doesn't contain Symbol %s, skipping" % symbol)
        continue
      sell_price = buy_price + round(float(self.stocks[symbol]["profit"]), 2)
      payload = self.conditional_order_payload(symbol, buy_price, sell_price, qty)

      # Placing the order
      url = self.base_url + "/orderexecution/orders"
      logging.debug(url)
      logging.debug(payload)
      res = requests.post(url, json=payload, headers=self.headers)
      status_code = res.status_code
      if status_code == 200:
        results = res.json()
      else:
        logging.error("Placing Order for %s for %s" % (symbol, buy_price))
        logging.error("Got the status code of %s" % status_code)
        logging.error(res.text)
      logging.info(results)
    

  # Get the current quote for the symbol(s)
  def get_quote(self, symbol=None):
    # Ensure we have working access token
    self.access_token = self.handle_auth()

    # Get quote from file
    self.quote = self.common.read_json(file=self.filename_quote)
    return self.quote

  def conditional_order_payload(self, symbol, buy_price, sell_price, qty):
    buy_price = round(float(buy_price),2)
    sell_price = round(float(sell_price),2)
    time_format = float(time.time())

    data = {
      "AccountID": self.account_id,
      "Symbol": symbol,
      "Quantity": "%s" % qty,
      "OrderType": "Limit",
      "TradeAction": "Buy",
      "LimitPrice": "%s" % buy_price,
      "Route": "Intelligent",
      "TimeInForce": {
        "Duration": "DAY"
      },
      "OSOs": [{
        "Type": "Normal",
        "Orders": [{
          "AccountID": self.account_id,
          "Symbol": symbol,
          "Quantity": "%s" % qty,
          "OrderType": "Limit",
          "TradeAction": "Sell",
          "LimitPrice": "%s" % sell_price,
          "Route": "Intelligent",
          "TimeInForce": {
            "Duration": "GTC"
          }
        }]
      }]
    }
    return data

  def get_buy_price(self, quote):
    return quote["Bid"]

  def get_sell_price(self, quote):
    return quote["Ask"]

  def get_orders(self):
    # Ensure we have working access token
    self.access_token = self.handle_auth()

    url = self.base_url + "/brokerage/accounts/%s/orders" % self.account_id
    res = requests.get(url, headers=self.headers)
    status_code = res.status_code
    if status_code == 200:
      results = res.json()
    else:
      logging.error("Placing Order for %s for %s")
      logging.error("Got the status code of %s" % status_code)
      logging.error(res.text)
    if "Orders" in results:
      self.orders = results["Orders"]
    return self.orders

  # Get the orders that are currently open
  def get_open_orders_by_symbol(self, symbol, orders=None):
    # Variables
    data = {}
    cur_time = self.get_date()

    # Ensure we have working access token
    self.access_token = self.handle_auth()

    url = self.base_url + "/brokerage/accounts/%s/positions" % self.account_id
    res = requests.get(url, headers=self.headers)
    status_code = res.status_code
    if status_code == 200:
      results = res.json()
    else:
      logging.error("Getting Open Positions for %s" % symbol)
      logging.error("Got the status code of %s" % status_code)
      logging.error(res.text)
      return data

    logging.debug("Get Open Positions")
    logging.debug(results)

    for each in results["Positions"]:
      # Verify position is from today
      pos_time = self.get_date(specific_date=each["Timestamp"])
      total_sec = (cur_time - pos_time).total_seconds()
      if total_sec > 35999:
        continue

      if symbol == each["Symbol"]:
        data[symbol] = each["Bid"]

    url = self.base_url + "/brokerage/accounts/%s/orders" % self.account_id
    res = requests.get(url, headers=self.headers)
    status_code = res.status_code
    if status_code == 200:
      results = res.json()
    else:
      logging.error("Getting Open Positions for %s" % symbol)
      logging.error("Got the status code of %s" % status_code)
      logging.error(res.text)
      return data

    for each in results["Orders"]:
      open_time = self.get_date(specific_date=each["OpenedDateTime"])
      total_sec = (cur_time - open_time).total_seconds()
      if total_sec > 35999:
        continue

      cur_status = each["Status"]
      cur_symbol = each["Legs"][0]["Symbol"]
      if cur_symbol not in data:
        if symbol == cur_symbol:
          if cur_status in self.status_list:
            buy_price = each["LimitPrice"]
            data[cur_symbol] = buy_price 

    return data

  # Cancel Open orders
  def cancel_orders(self, orders=None):
    logging.info("Begin Cancel Order Check")
    # Variables
    use_orders = {}
    cancel_order_list = []
    cur_date = self.get_date()

    # Ensure we have working access token
    self.access_token = self.handle_auth()
 
    # Get the orders from the broker
    if orders:
      logging.info("User Provided Orders, overwritting geting order from broker")
      use_orders = orders
    else:
      use_orders = self.get_orders()

    for each in use_orders:
      if each["Status"] in self.status_list:
        logging.info("Found an Open Status Order")
        if each["Legs"][0]["BuyOrSell"] == "Buy":
          logging.info("Found a Buy Order")
          logging.info("Reviewing order: %s, %s, %s, %s" % (each["OrderID"], each["Status"], each["Legs"][0]["BuyOrSell"], each["OpenedDateTime"]))
          order_opened = self.get_date(specific_date=each["OpenedDateTime"])
          seconds_since_open = (cur_date - order_opened).total_seconds()
          max_seconds_before_cancel = self.cancel_order_in_minutes * 60
          logging.info("Checking Times: %s -- %s" % (seconds_since_open, max_seconds_before_cancel))
          if seconds_since_open > max_seconds_before_cancel:
            cancel_order_list.append(each["OrderID"])

    for each in cancel_order_list:
      url = self.base_url + "/orderexecution/orders/%s" % each 
      res = requests.delete(url, headers=self.headers)
      status_code = res.status_code
      if status_code == 200:
        results = res.json()
        logging.info("Cancel Order %s" % each)
      else:
        logging.error("Cancel Order Failed for %s" % each)
        logging.error("Got the status code of %s" % status_code)
        logging.error(res.text)

  def market_open(self, delay=0):
    return self.finhub.market_open()

  # Get the open orders
  def check_open_orders(self, symbol=None):
    # Variables
    data = {}

    # Ensure we have working access token
    self.access_token = self.handle_auth()

    if not self.orders:
      self.get_orders()

    for each in self.orders:
      if each["Legs"]["OpenOrClose"] in self.status_list:
        if  each["Legs"]["BuyOrSell"] == "Buy":
          data[each["OrderID"]] = each
    return data


  # Get the amount of money able to be spend per day
  def get_spending_amount(self):
    # Variables
    spending_amount = 0

    # Ensure we have working access token
    self.access_token = self.handle_auth()

    url = self.base_url + "/brokerage/accounts/%s/balances" % self.account_id
    res = requests.get(url, headers=self.headers)
    status_code = res.status_code
    if status_code == 200:
      results = res.json()
    else:
      logging.error("Got the status code of %s" % status_code)
      logging.error(res.text)

    if "Balances" in results:
      for each in results["Balances"]:
        if each["AccountID"] == self.account_id:
          if self.account_type.lower() == "cash":
            spending_amount = round((float(each["CashBalance"]) / 2), 2)
          if self.account_type.lower() == "margin":
            spending_amount = round(float(self.file_data[self.broker]["spend_per_day"]), 2)
    return spending_amount

  def get_stock_price_gap(self, symbol, days_back = 120):
    # Variables
    data = {}

    # Ensure we have working access token
    self.access_token = self.handle_auth()

    url = self.base_url + "/marketdata/barcharts/%s" % symbol
    url += "?unit=Minute"
    #url += "&barsback=5000"
    url += "&sessiontemplate=Default"
    url += "&firstdate=%s" % self.get_date(days_back=days_back, raw_flag=False)
    url += "&lastdate=%s" % self.get_date(raw_flag=False)
    res = requests.get(url, headers=self.headers)
    status_code = res.status_code
    if status_code == 200:
      results = res.json()
    else:
      logging.error("Placing Order for %s for %s")
      logging.error("Got the status code of %s" % status_code)
      logging.error(res.text)

    logging.debug(results)

    for each in results["Bars"]:
      cur_open = float(each["Open"])
      cur_close = float(each["Close"])
      cur_change = round(float(cur_close - cur_open), 2)
      cur_change = abs(cur_change)
      try:
        data[cur_change] += 1
      except KeyError:
        data[cur_change] = 1
    return data


  def get_transactions(self, days_back=0, nextToken=None, data={}):
    # Variables
    group_array = {}  

    # Ensure we have working access token
    self.access_token = self.handle_auth()

    if days_back > 0: 
      url = self.base_url + "/brokerage/accounts/%s/historicalorders" % self.account_id
      url += "?since=%s" % self.get_date(days_back=days_back, raw_flag=False)
    else:
      url = self.base_url + "/brokerage/accounts/%s/orders" % self.account_id
    if nextToken:
      url += "&nextToken=%s" % nextToken
    logging.debug("Send Broker %s" % url)
    res = requests.get(url, headers=self.headers)
    status_code = res.status_code
    if status_code == 200:
      results = res.json()
    else:
      logging.error("Failure getting historical orders")
      logging.error("Got the status code of %s" % status_code)
      logging.error(res.text)

    logging.debug(json.dumps(results, indent=2))

    # Buy Loop 
    logging.info("Gather Buy Orders")
    for each in results["Orders"]:
      fees = 0
      order_id = each["OrderID"]
      logging.info("Reviewing Order: %s" % order_id)
      try:
        order_action = each["Legs"][0]["BuyOrSell"]
      except KeyError:
        logging.error("Non-Standard Order Found, Need human review")
        logging.error(json.dumps(each, indent=2))
        continue

      # Only handle the specific action
      if order_action.lower() == "buy":
        if order_id not in group_array:
          group_array[order_id] = {}

        try:
          group_array[order_id]["buy_price"] = float(each["Legs"][0]["ExecutionPrice"])
        except KeyError:
          group_array[order_id]["buy_price"] = float(each["LimitPrice"])

        group_array[order_id]["buy_qty"] = int(each["Legs"][0]["ExecQuantity"])
        group_array[order_id]["buy_status"] = each["StatusDescription"]
        group_array[order_id]["symbol"] = each["Legs"][0]["Symbol"]
        group_array[order_id]["open_time"] = each["OpenedDateTime"]
        fees += float(each["CommissionFee"])
        fees += float(each["UnbundledRouteFee"])
        group_array[order_id]["buy_fees"] = fees

    # Sell Loop
    logging.info("Gather Sell Orders")
    for each in results["Orders"]:
      try:
        buy_id = each["ConditionalOrders"][0]["OrderID"]
      except KeyError:
        logging.error("Missing Conditional Orders Section")
        logging.error(json.dumps(each, indent=2))
        continue

      try:
        order_action = each["Legs"][0]["BuyOrSell"]
      except KeyError:
        continue

      # Only handle the specific action
      if order_action.lower() == "sell":
        try:
          group_array[buy_id]["sell_price"] = float(each["Legs"][0]["ExecutionPrice"])
        except (TypeError, KeyError):
          group_array[buy_id]["sell_price"] = float(each["LimitPrice"])

        try:
          group_array[buy_id]["sell_qty"] = int(each["Legs"][0]["ExecQuantity"])
          group_array[buy_id]["sell_status"] = each["StatusDescription"]
          group_array[buy_id]["close_time"] = each["ClosedDateTime"]
        except KeyError:
          logging.error("Have a sell order without a buy order")
          logging.error(json.dumps(each, indent=2))

    logging.debug(json.dumps(group_array, indent=2))
    logging.info("Calculating results")    

    # Loop through parsed broker data
    for order_id, each_group in group_array.items():
      # Ensure the symbol is in the array
      cur_symbol = each_group["symbol"]
      if cur_symbol not in data:
        data[cur_symbol] = {}
        data[cur_symbol]["success_counter"] = 0
        data[cur_symbol]["total_counter"] = 0
        data[cur_symbol]["profit"] = 0

      # Total number of orders
      data[cur_symbol]["total_counter"] += 1

      # Sanity Check for odd orders
      try:
        cur_sell_status = each_group["sell_status"].lower()
      except KeyError:
        logging.debug(json.dumps(each_group, indent=2))
        logging.error("Only a buy value was found, Order ID: %s" % order_id)
        continue

      if cur_sell_status == "filled":
        if each_group["buy_qty"] == each_group["sell_qty"]:
          data[cur_symbol]["success_counter"] += 1
          total_buy_price = float(each_group["buy_price"]) * int(each_group["buy_qty"])
          total_sell_price = float(each_group["sell_price"]) * int(each_group["sell_qty"])
          data[cur_symbol]["profit"] += total_sell_price - total_buy_price
        else:
          logging.error("MisMatched Quality of Buy to Sell:")
          logging.error("Order ID: %s" % order_id)
          logging.error(json.dumps(each, indent=2))
      else:
        try:
          data[cur_symbol]["%s_counter" % each_group["sell_status"]] += 1
        except KeyError:
          data[cur_symbol]["%s_counter" % each_group["sell_status"]] = 1

      # Handle transaction times
      open_time = self.get_date(specific_date=each_group["open_time"])
      close_time = self.get_date(specific_date=each_group["close_time"])
      time_diff = (close_time - open_time).total_seconds()
      try:
        data[cur_symbol]["total_trans_sec"] += time_diff
      except KeyError: 
        data[cur_symbol]["total_trans_sec"] = time_diff

      avg_time = (data[cur_symbol]["total_trans_sec"] / data[cur_symbol]["total_counter"])
      data[cur_symbol]["avg_trans_per_sec"] = round(avg_time, 2)

      data[cur_symbol]["profit"] = round(data[cur_symbol]["profit"], 2)
 
      # Debugging
      logging.info("Reviewing Order: %s, Symbol: %s, Status: %s, Buy Price: %s, Sell Price: %s, Qty: %s, Profit: %s" % (order_id, cur_symbol, each_group["sell_status"], each_group["buy_price"], each_group["sell_price"], each_group["buy_qty"], data[cur_symbol]["profit"]))

    # Get Current Positions
    url = self.base_url + "/brokerage/accounts/%s/positions" % self.account_id
    logging.debug("Send Broker %s" % url)
    res = requests.get(url, headers=self.headers)
    status_code = res.status_code
    if status_code == 200:
      results = res.json()
    else:
      logging.error("Getting Open Positions")
      logging.error("Got the status code of %s" % status_code)
      logging.error(res.text)

    logging.debug(json.dumps(results, indent=2))
    if "Positions" in results:
      for each in results["Positions"]:
        try:
          data["Current_Positions"][each["Symbol"]] = each["Quantity"]
        except KeyError:
          data["Current_Positions"] = {}
          data["Current_Positions"][each["Symbol"]] = each["Quantity"]

    logging.debug(json.dumps(data, indent=2))
    return data


  # Get the date
    # timezone="America/New_York"
  def get_date(self, specific_date=None, mins_back=0, days_back=0, raw_flag=True, timezone="UTC", hour_format=False, timezone_format=False):
    # Local Variables   
    days_back = int(days_back)
    mins_back = int(mins_back)
 
    # Set Format
    use_format = "%Y-%m-%d"
    if hour_format:
      use_format += " %H:%M:%S"
    if timezone_format:
      use_format += " %z"

    # Get current date
    use_tz = pytz.timezone(timezone)
    if specific_date:
      try:
        if re.search("Z", specific_date):
          specific_date = re.sub("Z", "", specific_date)
        cur_date = datetime.datetime.fromisoformat(specific_date)
      except TypeError:
        if type(specific_date) == datetime.datetime:
          cur_date = specific_date
    else:
      cur_date = datetime.datetime.now(use_tz).strftime('%Y-%m-%dT%H:%M:%S')
      cur_date = datetime.datetime.fromisoformat(cur_date)
    backup_date = cur_date

    if mins_back > 0:
      cur_date = cur_date - datetime.timedelta(minutes=mins_back)

    if days_back > 0:
      cur_date = cur_date - datetime.timedelta(days=days_back)

    if raw_flag:
      return cur_date
    try:
      use_date = cur_date.strftime(use_format)
    except AttributeError:
      use_date = (backup_date - cur_date).strftime(use_format)

    return use_date


