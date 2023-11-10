# lazytrader

# Purpose
To allow a person to make micro trades between the buy and sell ranges of a stock

# Requirements
- Python 3
- Linux
- Active broker account (against one of the broker account classes)

# User Configuration
```
{
  "delay_market_open": <seconds>,
  "sleep_timer": <seconds>,
  "<broker>": {
    "sandbox": <true/false>,
    "account_id": "<Main Account ID",
    "dev_account_id": "<Sandbox Account ID>",
    "access_token": "<Main Account API Token>",
    "dev_access_token": "<Sandbox Account API Token>",
    "account_type": "<cash/margin>",
    "//spend_per_day": "for Non-Cash Accounts",
    "spend_per_day": <Max Margin Amount>,
    "cancel_order_in_minutes": <minutes>,
    "stocks": {
      "<symbol>": {
        "profit": <profit amount>,
        "stop_loss": <stop loss amount>,
        "qty": <shares per transaction>
      }
    }
  }
}

```

# User Configuration Terminology
| Term | Definition |
| broker | The company you use to buy and sell stocks with |
| delay_market_open | How long after the market open before starting to trade |
| sleep_timer | How long to wait between trades |
| sandbox | Test location to try out the system without using money |
| account_id | Depending on the broker if needed, your main account number |
| dev_account_id | Depending on the broker if needed, you sandbox account number |
| API key | A long set of letters and numbers which identify your account while trading |
| access_token | Depending on the broker if needed, the API key assocated with your main account |
| dev_access_token | Depending on the broker if needed, the API key assocated with your sandbox account |
| account_type | How you want the program to treat your account |
| cash | Specific account type, which uses half of the avaiable amount of money in your account per day |
| margin | Specific account type, which uses the amount you tell it |
| cancel_order_in_minutes | How long to wait with an open buy order, before sending a cancellation |
| symbol | Stock symbol you want traded |
| profit | The amount of money added to the buy price to determine the sell price |
| | Buy Price for APPL at 128.10, profit = .10, Sell Price for APPL is set 128.20 |
| stop_loss | Not yet added |
| qty | The total amount of shares to buy per transaction | 

# User Configuration Example
```
{
  "delay_market_open": 1200,
  "sleep_timer": 30,
  "tradier": {
    "sandbox": false,
    "account_id": "XXXXX",
    "dev_account_id": "XXXXXX",
    "access_token": "XXXXXXXXXXXXXXXXXXXXXXX",
    "dev_access_token": "XXXXXXXXXXXXXXXXXXXXXX",
    "account_type": "cash",
    "//spend_per_day": "for Non-Cash Accounts",
    "spend_per_day": 9999999999,
    "cancel_order_in_minutes": 15,
    "stocks": {
      "AMZN": {
        "profit": 0.05,
        "stop_loss": 0.5,
        "qty": 1
      },
      "AAPL": {
      "profit": 0.05,
      "stop_loss": 0.5,
      "qty": 1
      }
    }
  }
}

```

# Installation Steps
1. Add the lazytrader user with a home directory with bash
2. Download lazytrader from GitHub
3. Create user_config.json file in the lazytrader home directory
4. Add the cronjobs from the CRONTAB file
5. Test the trader, stats, and compare_gap scripts

# Installation Example
```
ssh root@192.169.1.2
adduser lazytrader
sudo su - lazytrader
git clone https://github.com/sldragon1234/lazytrader.git
vi user_config.json
cat CRONTAB
crontab -e
/home/lazytrader/lazytrader/trader.py -v
/home/lazytrader/lazytrader/stats.py -D 0 --email_bypass
/home/lazytrader/lazytrader/compare_gap.py -D 60 -s APPL
```
