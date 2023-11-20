#!/bin/env python3

# Modules
import re
import os
import sys
import uuid
import pytz
import logging
import requests
import datetime
from pprint import pprint

# Custom Modules
#sys.path.append(os.path.expanduser('~') + "/lazytrader")
sys.path.append(os.path.expanduser('~') + "/lazytrader-unreleased")

class TRADIER_CLASS:
  # Variables
  file_data = None
  broker = "tradier"
  max_trans_in_sec = 28800
  neg_status_list = ["open", "held", "pending"]

  # Request Variables
  scope = "trade, market"
  headers = {"Accept": "application/json"}
  base_url = "https://api.tradier.com"
  sandbox_base_url = "https://sandbox.tradier.com"

  # Config Variables
  access_token = None
  account_id = None
  account_type = None
  spend_per_day = None

  # Trade Variables
  orders = None
  current_spend = 0

  def __init__(self, file_data=None):
    if file_data:
      self.file_data = file_data

    # Set Variables
    self.access_token = self.file_data[self.broker]["access_token"]
    self.account_id = self.file_data[self.broker]["account_id"]
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

  # Place Buy Order
  def place_orders(self):
    # Variables
    buy_price = 0

    # Get Transaction Orders
    self.orders = self.get_orders()

    # Get Current Quotes
    quote = self.get_quote(self.stock_list)

    for symbol in self.stock_list:
      # Get Open Order for a Symbol
      res = self.get_open_orders_by_symbol(symbol, self.orders)

      # Skip Open Orders
      if len(res) > 0:
        logging.debug("Found Open Position for %s" % symbol)
        continue
     
      # Get Order Variables
      profit = self.file_data[self.broker]["stocks"][symbol]["profit"]
      qty = self.file_data[self.broker]["stocks"][symbol]["qty"]
      buy_price = self.get_buy_price(quote[symbol]) 
      sell_price = buy_price + profit

      # Verify we have funds to place an order
      avail_spend = self.spend_per_day - self.current_spend
      want_spend = buy_price * qty
      logging.debug("Buy Logic %s: %s > %s and %s > %s" % (symbol, self.spend_per_day, self.current_spend, avail_spend, want_spend))
      if self.spend_per_day > self.current_spend and avail_spend > want_spend:
        # Place Order with Broker
        self.conditional_order_payload(symbol, buy_price, sell_price, qty)
        self.current_spend += buy_price
        logging.info("Buy %s for %s, Spend %s out of %s" % (symbol, buy_price, self.current_spend, self.spend_per_day))
    return buy_price

  # Cancel Old Orders
  def cancel_orders(self):
    cancel_amount = 0

    # Get Transaction Orders
    self.orders = self.get_orders()

    for symbol in self.stock_list:
      # Re-Initialize Variables
      return_amount = 0

      # Get Open Order for a Symbol
      res = self.get_open_orders_by_symbol(symbol, self.orders)

      # Skip empty symbols
      if len(res) == 0:
        continue
      
      # Cancel Transactions
      return_amount = self.cancel_order(symbol, self.orders)
      if return_amount > 0:
        self.current_spend = round(float(self.current_spend - return_amount), 2)
        cancel_amount += return_amount
        logging.info("Cancel %s for %s, Spend %s out of %s" % (symbol, return_amount, self.current_spend, self.spend_per_day))

    return cancel_amount

  # Get the quote from broker
  def get_quote(self, symbol=None):
    data = {}
    # Verify User Input
    if not symbol:
      logging.error("No Symbol has been provided")
      return None

    # Variables 
    url = "%s/v1/markets/quotes" % self.base_url
    payload = {}

    # Return the results from the symbol
    if type(symbol) is list:
      symbol = ",".join(symbol)
    payload["symbols"] = symbol
    results = requests.get(url, params=payload, headers=self.headers).json()

    for key, each in results["quotes"].items():
      if type(each) == list:
        for current in each:
          data[current["symbol"]] = current
      else:
        data[each["symbol"]] = each
    return data

  # Place a triggered order with broker
  def conditional_order_payload(self, symbol, buy_price, sell_price, qty):
    url = "%s/v1/accounts/%s/orders" % (self.base_url, self.account_id)
    payload = {
      "class": "oto"
    }

    # Buy Side
    payload["type[0]"] = "limit"
    payload["side[0]"] = "buy"
    payload["symbol[0]"] = symbol
    payload["quantity[0]"] = qty
    payload["duration[0]"] = "day"
    payload["price[0]"] = round(float(buy_price), 2)

    # Sell Side
    payload["type[1]"] = "limit"
    payload["side[1]"] = "sell"
    payload["symbol[1]"] = symbol
    payload["quantity[1]"] = qty
    payload["duration[1]"] = "gtc"
    payload["price[1]"] = round(float(sell_price), 2)
    logging.debug("Sending URL: %s" % url)
    logging.debug("Sending Headers: %s" % self.headers)
    logging.debug("Sending Payload: %s" % payload)
    results = requests.post(url, data=payload, headers=self.headers).json()
    logging.debug("Return Results: %s" % results)
    return results

  # Get the buy price from the quote
  def get_buy_price(self, quote):
    return round(float(quote["bid"]), 2)

  def get_sell_price(self, quote):
    return round(float(quote["ask"]), 2)

  def get_orders(self):
    # Variables
    data = {}
    url = "%s/v1/accounts/%s/orders" % (self.base_url, self.account_id)
    payload = {"includeTags": "false"}

    # Get current date
    cur_date = self.get_data()
    #use_tz = pytz.timezone('UTC')
    #cur_date = datetime.datetime.now(use_tz).strftime('%Y-%m-%dT%H:%M:%S')
    #cur_date = datetime.datetime.fromisoformat(cur_date)

    # Get the data from the broker
    results = requests.get(url, headers=self.headers).json()

    if results["orders"] == 'null':
      return data

    # Force a single entry into a list
    if type(results["orders"]["order"]) is not list:
      results["orders"]["order"] = [results["orders"]["order"]]

    # Parse the results
    for each in results["orders"]["order"]:
      cur_id = each["id"]
      cur_symbol = each["leg"][0]["symbol"]
      buy_status = each["leg"][0]["status"]
      sell_status = each["leg"][1]["status"]
      sell_amount = float(each["leg"][1]["price"]) * float(each["leg"][1]["quantity"])
      buy_amount = float(each["leg"][0]["price"]) * float(each["leg"][0]["quantity"])
      #trans_date = each["leg"][0]["create_date"]
      trans_date = each["leg"][0]["transaction_date"]
      trans_date = re.sub("\.\w+$", "", trans_date)
      use_date = self.get_data(specific_date=trans_date)
      sell_date = each["leg"][1]["transaction_date"]
      sell_date = re.sub("\.\w+$", "", sell_date)
      sell_date = self.get_data(specific_date=sell_date)

      # Build the active order array
      try:
        data[cur_symbol].append({"id": cur_id, "buy_status": buy_status, "sell_status": sell_status, "date": trans_date, "buy_amount": buy_amount, "sell_amount": sell_amount, "sell_date": sell_date, "buy_date": use_date})
      except KeyError:
        data[cur_symbol] = []
        data[cur_symbol].append({"id": cur_id, "buy_status": buy_status, "sell_status": sell_status, "date": trans_date, "buy_amount": buy_amount, "sell_amount": sell_amount, "sell_date": sell_date, "buy_date": use_date})
    return data

  # Get the open order by symbol
  def get_open_orders_by_symbol(self, symbol, orders=None):
    # Variables
    data = {}

    # Get current date
    cur_date =  self.get_data()
    #use_tz = pytz.timezone('UTC')
    #cur_date = datetime.datetime.now(use_tz).strftime('%Y-%m-%dT%H:%M:%S')
    #cur_date = datetime.datetime.fromisoformat(cur_date)

    if not orders:
      orders = self.get_orders()

    # Get User specific symbols if provided
    for cur_symbol, each in orders.items():
      # Re-Initalize Variables
      pos_flag = False
      if cur_symbol.upper() == symbol.upper():

        for entry in each:
          use_date = self.get_data(specific_date=entry["date"])
          #use_date = datetime.datetime.fromisoformat(entry["date"])

          # Verify if the transaction is too old
          trans_in_seconds = (cur_date - use_date).total_seconds()
          if trans_in_seconds >= self.max_trans_in_sec:
            logging.debug("Transaction in seconds: %s, vs Max Transaction in seconds: %s" % (trans_in_seconds, self.max_trans_in_sec))
            logging.debug("Old Order, Skipping")
            continue

          if entry["buy_status"] not in self.neg_status_list:
            if entry["sell_status"] in self.neg_status_list:
              pos_flag = True
          else: 
            pos_flag = True

          # Add Position to List
          if pos_flag:
            try:
              data[cur_symbol].append(each)
            except KeyError:
              data[cur_symbol] = []
              data[cur_symbol].append(each)
    return data

  def cancel_order(self, symbol, orders=None):
    # Variables
    order_id = None
    results = None
    cancel_amount = 0

    # Get current date
    cur_date = self.get_data()
    #use_tz = pytz.timezone('UTC')
    #cur_date = datetime.datetime.now(use_tz).strftime('%Y-%m-%dT%H:%M:%S')
    #cur_date = datetime.datetime.fromisoformat(cur_date)

    # Get orders from broker
    if not orders:
      orders = self.get_orders()

    # Get an array of order
    orders_array = self.get_open_orders_by_symbol(symbol=symbol, orders=orders)

    # Force single orders into a list   
    try: 
      if type(orders_array[symbol]) is not list:
        orders_array[symbol] = orders_array[symbol]
    except KeyError:
      logging.debug("No orders found for %s" % symbol)
      return False

    # Parse if an order needs to be canceled
    for index in orders_array[symbol]:
      for each in index:
        if each["buy_status"] not in self.neg_status_list:
          continue

        # Get transaction date
        trans_date = self.get_data(specific_date=each["date"])
        #trans_date = datetime.datetime.fromisoformat(each["date"])
        cancel_date = self.get_data(mins_back=self.cancel_order_in_minutes)
        #cancel_date = datetime.timedelta(minutes=self.cancel_order_in_minutes)
        cancel_in_sec = (cur_date - (trans_date + cancel_date )).total_seconds()
        logging.debug("Cancel Order Logic: %s > 0" % cancel_in_sec) 
        if cancel_in_sec > 0:        
          logging.debug("Checking the current order")
          logging.debug(each)
          logging.debug("------------------------------")
          order_id = each["id"]
          cancel_amount += each["buy_amount"]
          url = "%s/v1/accounts/%s/orders/%s" % (self.base_url, self.account_id, order_id)
          requests.delete(url, headers=self.headers)

    return cancel_amount

  # Check if the market is open
  def market_open(self, delay=0):
    # Variables
    is_open = False
    market_status = False

    # Get current date
    cur_date = self.get_data(timezone="America/New_York")
    #use_tz = pytz.timezone('America/New_York')
    #cur_date = datetime.datetime.now(use_tz).strftime('%Y-%m-%dT%H:%M:%S')
    #cur_date = datetime.datetime.fromisoformat(cur_date)
    use_date = cur_date.strftime("%Y-%m-%d")

    # Get the market status from broker
    logging.debug("Getting the calendar from the broker")
    url = "%s/v1/markets/calendar" % self.base_url
    results = requests.get(url, headers=self.headers).json()

    # Parse the broker market start time
    logging.debug("Parsing the calender from broker")
    for each in results["calendar"]["days"]["day"]:
      if each["date"] == use_date:
        logging.debug("Checking if the market is open")
        logging.debug(each)
        if each["status"] == "open":
          is_open = True
        start_date = self.get_data(specific_date="%s %s" % (each["date"], each["open"]["start"]))
        start_date = datetime.datetime.fromisoformat("%s %s" % (each["date"], each["open"]["start"]))
        end_date = self.get_data(specific_date="%s %s" % (each["date"], each["open"]["end"]))
        #end_date = datetime.datetime.fromisoformat("%s %s" % (each["date"], each["open"]["end"]))
        logging.debug("Market Open from Broker: is_open %s - start_date %s - end_date %s" % (is_open, start_date, end_date))
        
    logging.debug("Current Date: %s" % cur_date)
    # Determine if the market is open
    logging.debug("Checking if market is open")
    if cur_date >= start_date and cur_date <= end_date and is_open:
      market_status = True
    if (cur_date - start_date).total_seconds() <= delay:
      market_status = False    
    logging.debug("Returning Market Open Status: %s" % market_status) 
    return market_status

  # Get a list of open positions
  def check_open_orders(self, symbol=None):
    positions = []

    # Get current date
    cur_date = self.get_data(timezone="America/New_York")
    #use_tz = pytz.timezone('America/New_York')
    #cur_date = datetime.datetime.now(use_tz).strftime('%Y-%m-%dT%H:%M:%S')
    #cur_date = datetime.datetime.fromisoformat(cur_date)

    # Get the current open positions from broker
    url = "%s/v1/accounts/%s/positions" % (self.base_url, self.account_id)
    results = requests.get(url, headers=self.headers).json()

    # Check for any open positions
    if results["positions"] == "null":
      return positions

    # Parse the position data and build
    if symbol:
      for each in results["positions"]["position"]:
        if each["symbol"] == symbol:
          positions.append(each["symbol"])
    else:
      for each in results["positions"]["position"]:
        pos_date = self.get_data(specific_date=each["date_acquired"])
        pos_date = datetime.datetime.fromisoformat(each["date_acquired"])
        if (cur_date - pos_date).total_seconds() < 28800:
          positions.append(each["symbol"])
    return positions

  # Get the amount which can be spend for the day
  def get_spending_amount(self):
    #pprint(self.account_type.lower())
    if self.account_type.lower() == "cash":
      url = "%s/v1/accounts/%s/balances" % (self.base_url, self.account_id)
      results = requests.get(url, headers=self.headers).json()
      #pprint(results)
      try:
        return round((float(results["balances"]["cash"]["cash_available"]) / 2), 2)
      except KeyError:
        return round((float(results["balances"]["total_cash"]) / 2), 2)
    return self.spend_per_day

  # Get the price grap array
  def get_stock_price_gap(self, symbol, days_back = 120):
    # Variables
    data = {}
    days_back = int(days_back)
    old_price = 0

    url = "%s/v1/markets/timesales" % (self.base_url)
    payload = {}
    payload["symbol"] = symbol
    payload["interval"] = "1min"
    payload["end"] = self.get_data(raw_flag=False, hour_format=True)[:-3]
    payload["start"] = self.get_data(days_back=days_back, raw_flag=False, hour_format=True)[:-3]

    logging.debug("URL: %s" % url)
    logging.debug("Payload %s" % payload)
    logging.debug("Headers: %s" % self.headers)

    try:
      #results = requests.get(url, data=payload, headers=self.headers)
      results = requests.get(url, params=payload, headers=self.headers)
      results = results.json()
    except Exception as e:
      logging.error("Broker Error: %s - %s" % (results.status_code, results.text))

    if "series" not in results:
      logging.error("No Historicial Data Available")
      return data

    for each in results["series"]["data"]:
       price_open = round(float(each["open"]), 2)
       price_close = round(float(each["close"]), 2)
       price_gap = round(float(price_close - price_open), 2)
       price_gap = abs(price_gap)  
       try:
         data[price_gap] += 1
       except KeyError:
         data[price_gap] = 1
    return data

  # Get the transactions of the account
  def get_transactions(self, days_back=0):
    # Variables
    data = {}
    gainloss = None

    # Date Variables
    cur_date = self.get_data()
    if days_back == 0:
      midnight = cur_date.strftime('%Y-%m-%dT00:00:00')
      start_date = self.get_data(specific_date=midnight)
    else:
      minutes_back = days_back * 1440
      start_date = (cur_date - self.get_data(mins_back=minutes_back))

    if days_back > 0:
      # Get Settled Closed Orders
      url = "%s/v1/accounts/%s/gainloss" % (self.base_url, self.account_id)
      results = requests.get(url, headers=self.headers).json()
      if "gainloss" not in results:
        logging.info("No Stat Activity Avaiable")
        return data

      # Standard the output
      if type(results["gainloss"]["closed_position"]) is not list:
        gainloss = [results["gainloss"]["closed_position"]]
      else:
        gainloss = results["gainloss"]["closed_position"]

      # Parse the transactions
      for each in gainloss:
        cur_symbol = each["symbol"]
        if cur_symbol not in data:
          data[cur_symbol] = {}

        open_date = each["open_date"][:-5]
        open_date = self.get_data(specific_date=open_date)
        close_date = each["close_date"][:-5]
        close_date = self.get_data(specific_date=close_date)
        trans_time = (close_date - open_date).total_seconds()
        num_days = abs((start_date - close_date).days)

        if num_days <= days_back:
          try:
            data[cur_symbol]["success_counter"] += 1
            data[cur_symbol]["total_trans_counter"] += 1
            data[cur_symbol]["total_trans_time"] += trans_time
          except KeyError:
            data[cur_symbol] = {}
            data[cur_symbol]["success_counter"] = 1
            data[cur_symbol]["total_trans_counter"] = 1
            data[cur_symbol]["total_trans_time"] = trans_time

    # Get current orders
    orders = self.get_orders()
    for cur_symbol in orders:
      if cur_symbol not in data:
        data[cur_symbol] = {}
      for entry in orders[cur_symbol]:
        try:
          data[cur_symbol]["total_trans_counter"] += 1
        except KeyError:
          data[cur_symbol]["total_trans_counter"] = 1

        if entry["sell_status"] == "filled":
          cur_profit = entry["sell_amount"] - entry["buy_amount"]
          trans_time = (entry["sell_date"] - entry["buy_date"]).total_seconds()

          try:
            data[cur_symbol]["success_counter"] += 1
            data[cur_symbol]["total_trans_time"] += trans_time
          except KeyError:
            data[cur_symbol] = {}
            data[cur_symbol]["success_counter"] = 1
            data[cur_symbol]["total_trans_time"] = trans_time

    # Get Open Positions     
    url = "%s/v1/accounts/%s/positions" % (self.base_url, self.account_id)
    results = requests.get(url, headers=self.headers).json()
    if results["positions"] == "null":
      return data

    # Standard the output
    if type(results["positions"]["position"]) is not list:
      positions = [results["positions"]["position"]]
    else:
      positions = results["positions"]["position"]

    
    for each in positions:
      cur_symbol = each["symbol"]
      acquired = each["date_acquired"][:-5]
      acquired = self.get_data(specific_date=acquired)
      num_days = abs((start_date - acquired).days)
      if num_days > days_back:
        try:
          data[cur_symbol]["old_order_counter"] += 1
        except KeyError:
          data[cur_symbol]["old_order_counter"] = 1
        data[cur_symbol]["total_trans_counter"] += 1

    # Additional Calculations
    for cur_symbol in data:
      profit_amount = self.file_data[self.broker]["stocks"][cur_symbol]["profit"]
      total_trans_count = data[cur_symbol]["total_trans_counter"]
      total_success = data[cur_symbol]["success_counter"]
      data[cur_symbol]["failure_count"] = total_trans_count - total_success
      data[cur_symbol]["success_percentage"] = round(float((total_success / total_trans_count) * 100), 2)
      data[cur_symbol]["average_trans_time"] = round(float(trans_time) / int(total_trans_count), 2)
      data[cur_symbol]["profit"] = round(float(total_success * profit_amount), 2)

      # Remove placeholders
      del data[cur_symbol]["total_trans_time"]
    return data

  # Get the date
  def get_data(self, specific_date=None, mins_back=0, days_back=0, raw_flag=True, timezone="UTC", hour_format=False, timezone_format=False):
    # Set Format
    use_format = "%Y-%m-%d"
    if hour_format:
      use_format += " %H:%M:%S"
    if timezone_format:
      use_format += " %z"

    # Get current date
    use_tz = pytz.timezone(timezone)
    if specific_date:
      cur_date = datetime.datetime.fromisoformat(specific_date)
    else:
      cur_date = datetime.datetime.now(use_tz).strftime('%Y-%m-%dT%H:%M:%S')
      cur_date = datetime.datetime.fromisoformat(cur_date)
    backup_date = cur_date

    if mins_back > 0:
      cur_date = datetime.timedelta(minutes=mins_back)

    if days_back > 0:
      cur_date = datetime.timedelta(days=days_back)

    if raw_flag:
      return cur_date
    try:
      use_date = cur_date.strftime(use_format)
    except AttributeError:
      use_date = (backup_date - cur_date).strftime(use_format)

    return use_date
   
if __name__ == "__main__":
  # Custom Modules
  sys.path.append(os.path.expanduser('~') + "/lazytrader")
  import common_class

  # Variables
  symbol_group = ["AAPL"]
  #symbol = "TSLA"
  symbol = "AAPL"
  buy_price = 10
  sell_price = 15
  qty = 1
  user_config = os.path.expanduser('~') + "/lazytrader-unreleased/user_config.json"

  # Enable logging
  log_level = logging.DEBUG
  logging.basicConfig(level=log_level)

  # Initalize Common Class
  common_class = common_class.COMMON()

  # Initalize user config data
  file_data = common_class.get_user_data(user_config)
  logging.debug("User Config Data from: %s" % user_config)
  logging.debug(file_data)

  # Initalize Class
  tradier = TRADIER_CLASS(file_data=file_data)

  # Get Quote
  #pprint(tradier.get_quote(symbol_group))
  #pprint(tradier.get_quote(symbol))

  # Market Open
  #pprint(tradier.market_open())

  # Get Daily Spending
  #pprint(tradier.get_spending_amount())

  # Place Order
  #pprint(tradier.conditional_order_payload(symbol, buy_price, sell_price, qty))

  # Get Orders
  #pprint(tradier.get_orders())

  # Get Orders By Symbol
  #pprint(tradier.get_open_orders_by_symbol(symbol))

  # Cancel Order
  #pprint(tradier.cancel_order(symbol))
