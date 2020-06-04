This is an unplanned tool that sprouted when I was playing with Python and Binance API and realized that there are many financial 
things that I perform so frequently, wouldn't it be nice to just fire a command from you Phone and response is sent withing seconds on the same screen ?
Or what about scheduling something to run over and over without having to remember it.

This tool is a Telegram bot, that supports many commands which can be sent to it from Telegram by authorized handles only.
The Backend APIs are provided by Binance which supports quite a lot of features for Cryptocurrency Markets.

# Prerequisites of this Tool
- A Telegram Bot and Its API Key
- Binance Account and API Key and Secret

# Running the tool
1. Install Dependencies `pip install -r requirements.txt`
2. Run the script `python bot.py --log=INFO|DEBUG`  
In case you haven't configured it already, you will get a message.
Please follow the next section for Configuration.

# Configuration
The Configuration is a JSON file maintained at the following location: `config/config.json`. 
The directory also contains a Template file which should be used to configure it.

Please fill the following details in the config file.
```
  "telegramApiKey": "----",
  "binanceApiKey": "----",
  "binanceApiSecret": "----",
  "adminUserId": "----"
```

You can also provide some other UserIDs to give access to other accounts for certain Commands.
You can create a named group under accessContro.groups node and provide a list of telegram userIDs. 
```
  "accessControl": {
    "groups": {
    "private": [ "----","---"],
    ...
```

# Features Overview
- Provide many useful features that a trader might be interested in without having to check it manually 
- Provides simple commands which can be used through telegram bot, check the Commands in Next section
- Provides the indicator of price movement over a threshold
- Provide technical Analysis of the assets using TA
 - MACD Crossover
 - RSI
 - Bollinger Bands
- Provide Account management on Binance
- Schedule a Command that runs periodically
- Place Buy / Sell Order using simple commands

# Commands
## Asset Management Commands
| Command  | Details| Examples |
| :---- | :---- | :----|
| symboladd | adds a Symbol in local store     | `/symboladd ADA`   |
| symbolrm  | remove a Symbol in local store   | `/symbolrm ADA`  |
| now       | Current Price of all Assets in USD      | `/now` |
| hot       | Any movement in prices in last x minutes above threshold | `/hot 5m 6 3` All movements of 3% in 4x5m window |

## Trading Commands
| Command  | Parameters| Examples |
| :---- | :---- | :----|
|   |   |   |
|   |   |   |
## Technical Analysis Commands
| Command  | Parameters| Examples |
| :---- | :---- | :----|
|   |   |   |
|   |   |   |
## Scheduling
| Command  | Parameters| Examples |
| :---- | :---- | :----|
|   |   |   |
|   |   |   |
## Conditional Commands
| Command  | Parameters| Examples |
| :---- | :---- | :----|
|   |   |   |
|   |   |   |


# Dependent Modules
- Finta: For all Financial Technical Analysis using KLINES
- schedule: For scheduling Tasks
- python-binance: For Connecting to Binance
- mplfinance: For Klines charts
- matplotlib: for Plottign the Charts and generating Images 

# ToDo
- publish it as a Python module
- Provider instructions for running as a Docker image