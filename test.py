import os

from lib import app

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
