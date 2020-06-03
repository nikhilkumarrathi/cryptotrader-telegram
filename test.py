import os

from lib import app


# import coins
# symbols = coins.coins
# for x in symbols:
#     print(app.price_alert(f'{x}USDT', timeframe='1h', count=12, threshold=0))
# klines = app.klines('ADAUSDT', '4h', 1000)
# df = app.dataframe(klines)
# from finta import TA
# TA.BBANDS(df).plot()
# tp.plot(range(0, len(klines)), [float(x[4]) for x in klines])
# plx.scatter(range(0, len(klines)), [float(x[4]) for x in klines], cols=90, rows=30)
# plx.show()
# import commands
# commands.run_command("tahints", ['AION', '1d', '200'])
# commands.run_command("candles", ['AION', '15m', '100'])
# commands.run_command("candles", ['AION', '15m', '150'])
# commands.run_command("ta", "ada".split(" "))
# orders = app.get_open_orders(side='BUY')
# if len(orders) > 0:
#     order = orders[0]
#     price = order['price']
#     symbol = order['symbol']
#     origQty = order['origQty']
#     executedQty = order['executedQty']
#     currPrice = app.tickers()[symbol]
# when currPrice to price diff > threshld%import charts
# # signal = charts.macd_x_over('ADAUSDT','1h',1000)
# # print(signal)
# place a new order of the same amount ( price*origQty ) with new price (currPrice - threshld%)
#

def adjust_price_near_market(inputPrice, currencyPrice):
    attempts = 0
    while attempts < 10:
        attempts = attempts + 1
        if 0.9 * currencyPrice <= inputPrice <= 1.1 * currencyPrice:
            return inputPrice

        if inputPrice > currencyPrice:
            inputPrice = inputPrice / 10
        else:
            inputPrice = inputPrice * 10


currencyPrice = app.tickers()['AIONBTC']
print('currency Price:', currencyPrice)
inputPrice = 1.67
print('input Price:', inputPrice)

adjusted = adjust_price_near_market(1, currencyPrice)
print('adjusted Price:', adjusted)
os._exit(0)
