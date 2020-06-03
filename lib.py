import datetime
import json
import math
import re
import urllib.parse
import urllib.request
from decimal import *
from typing import *

import binance
import numpy as np
import pandas as pd
import requests
from binance.client import Client
from dotmap import DotMap
from config import configData

import log
from db import db, Const


def default_config():
    return {
        "telegram_last_update_id": 0,
        "symbols": ["ADA"]
    }


class App:
    def __init__(self):
        self.client = Client(configData.binanceApiKey, configData.binanceApiSecret, {"timeout": 20})
        self.telegramKey = configData.telegramApiKey
        self.data = DotMap()

    def klines(self, symbol, timeframe='5m', count=12):
        """ Return Klines for the given timeframe and count
            [[Open time,Open,High,Low,Close,Volume, ...]]"""
        res = re.search(r'(\d+)([mhdw])', timeframe)
        num = res.group(1) if res else "5"
        time_format = res.group(2) if res else "m"
        time_str = 'minutes'
        if time_format == 'h':
            time_str = 'hours'
        elif time_format == 'd':
            time_str = 'days'
        elif time_format == 'w':
            time_str = 'weeks'

        time_ago_str = f'{count * int(num)} {time_str} ago'
        log.debug("getting klines: %s %s '%s' %s", symbol, timeframe, time_ago_str, count)
        klines = self.client.get_historical_klines(symbol, timeframe, time_ago_str, limit=count)
        return klines

    def tickers(self):
        return {x['symbol']: float(x['price']) for x in self.client.get_all_tickers()}

    @staticmethod
    def floor(number, digits=2):
        return int(math.floor(float(number) * (10 ** digits))) / (10 ** digits + 0.0)

    @staticmethod
    def floor_new(number, digits=2):
        return str(Decimal(number).quantize(Decimal(1) / Decimal(10 ** digits), rounding=ROUND_DOWN))

    def place_order(self, orderObj, priceDigits=10, qtyDigits=4, test=True):
        """ Place and order to binance with the given Order and minimum significan number for quantity and price in
        digits.If error is due to price and quantity notional value then it will be attempted again by reducing the notional digits"""
        while qtyDigits >= 0 or priceDigits >= 0:
            if 'stopPrice' in orderObj:
                orderObj['stopPrice'] = (self.floor_new(orderObj['stopPrice'], priceDigits))
            orderObj['price'] = (self.floor_new(orderObj['price'], priceDigits))
            orderObj['quantity'] = (self.floor_new(orderObj['quantity'], qtyDigits))
            try:
                if (test):
                    self.client.create_test_order(**orderObj)
                    log.info(orderObj)
                    return orderObj
                else:
                    self.client.create_order(**orderObj)
                    return orderObj
                break
            except binance.exceptions.BinanceAPIException as e:
                if ('PRICE_FILTER' in e.message or 'Precision' in e.message):
                    priceDigits = priceDigits - 1
                elif ('LOT_SIZE' in e.message):
                    qtyDigits = qtyDigits - 1
                else:
                    log.error("** cannot place Order **")
                    log.error(e)
                    orderObj['quantity'] = 0
                    return orderObj
                    break
                log.debug("retrying order %s , %s", orderObj['price'], orderObj['quantity'])

    def get_free_balances_non_usdt(self, worth_threshold=10):
        """ find balances from Binance account which are non USDT 
        and the worth of them in amount meets the threshold """
        account = self.client.get_account()
        tickers = self.tickers()
        balances = [(x['asset'], float(x['free']), float(x['locked']))
                    for x in account['balances'] if x['asset'] != 'USDT']
        freebalances = []
        for x in balances:
            symbol = x[0] + self.base_token(x[0], tickers)
            if symbol in tickers:
                amomunt = x[1] * tickers[symbol] if 'USDT' in symbol else (x[1] * tickers[symbol]) * tickers['BTCUSDT']
                if (amomunt) > worth_threshold:
                    freebalances.append((symbol, x[1], amomunt))

        return freebalances

    def create_stop_loss_orders(self, test=True, stoploss_prc=3.0, quantity_prc=100, symbols=None):
        """Find all Free Balances and create Stop Loss Orders"""
        free_balances = self.get_free_balances_non_usdt()
        tickers = self.tickers()
        log.debug("free balances: %s", free_balances)
        log.debug("required orders: %s", symbols)
        res = []
        for x in free_balances:
            if symbols and x[0] not in symbols:
                continue

            log.info('-- creating order for %s--', x[0])
            sym = x[0]
            action = 'SELL'
            sprice = (100 - stoploss_prc) / 100.0 * tickers[sym]
            price = (100 - stoploss_prc - 0.1) / 100.0 * tickers[sym]
            qty = x[1]
            orderObj = {'symbol': sym,
                        'quantity': float(qty) * quantity_prc / 100,
                        'side': action,
                        'type': 'STOP_LOSS_LIMIT',
                        'stopPrice': sprice,
                        'price': price,
                        'timeInForce': 'GTC'}
            curr_res = self.place_order(orderObj, test=test)
            res.append(curr_res)
        return res

    def send_msg(self, msg, chat_id, reply_message_id=None):
        """ 
        Sends message to Telegram group
        Emojis:
        https://apps.timwhitlock.info/emoji/tables/unicode

        """
        log.debug("sending message %s", msg)
        url = f"https://api.telegram.org/bot{self.telegramKey}/sendMessage?chat_id={chat_id}&parse_mode=Markdown&text="

        url += urllib.parse.quote('\n' + msg)
        if reply_message_id:
            url += f'&reply_to_message_id={reply_message_id}'
        with urllib.request.urlopen(url) as response:
            pass

    def send_photo(self, filename, chat_id, caption=""):
        url = f"https://api.telegram.org/bot{self.telegramKey}/sendPhoto?chat_id={chat_id}&caption={urllib.parse.quote(caption)}"
        response = requests.post(url, files={'photo': open(filename, 'rb')})

    def notify_action(self, chat_id):
        """
        Sends message to Telegram group
        """
        url = f"https://api.telegram.org/bot{self.telegramKey}/sendChatAction?chat_id={chat_id}&action=typing"
        # https://apps.timwhitlock.info/emoji/tables/unicode
        with urllib.request.urlopen(url) as response:
            pass

    def get_messages(self, offset=0, timeout=10):
        """ 
        Get notifications from Telegram after the provided offset   
        @return: Tuple( offset, author, chat_id, text, date )
        """
        urlString = f"https://api.telegram.org/bot{self.telegramKey}/getUpdates?offset={offset}&timeout={timeout}"
        try:
            with urllib.request.urlopen(urlString) as response:
                jsonObj = json.loads(response.read().decode('utf-8'))
                response = []
                for x in jsonObj['result']:
                    log.debug("From Telegram: message: %s", x)
                    if 'message' in x:
                        message = DotMap(x['message'])
                        message.update_id = x['update_id']
                        if message.entities:
                            del message.entities
                        if message['from'].first_name:
                            del message['from'].first_name
                        if message['from'].last_name:
                            del message['from'].last_name
                        if message['chat'].first_name:
                            del message['chat'].first_name
                        if message['chat'].last_name:
                            del message['chat'].last_name
                        response.append(message)
                    else:
                        response.append(DotMap({'update_id': x['update_id']}))

                    if 'callback_query' in x:
                        log.info(json.dumps(x))

                return response
        except Exception as e:
            log.error(e)
            return []

    @staticmethod
    def timestamp_to_str(ts: float, fmt: str = '%Y-%m-%d %H:%M:%S'):
        return datetime.datetime.fromtimestamp(ts).strftime(fmt)

    def to_amount(self, symbol, balance, tickers):
        if symbol == 'USDT':
            return self.floor(balance, 2)
        elif symbol == 'BTC':
            return self.floor(balance * tickers["BTCUSDT"], 2)
        elif symbol + 'BTC' in tickers:
            return self.floor(balance * tickers[symbol + 'BTC'] * tickers["BTCUSDT"], 2)
        else:
            return 0.0

    def get_account_balances(self):
        """
        Tuple( Symbol, Free , Locked, Free+Locked )
        """
        account = self.client.get_account()
        balances = ((x['asset'], float(x['free']), float(x['locked']), float(x['free']) + float(x['locked']))
                    for x in account['balances'])
        return balances

    def get_snapshot(self):
        balances = self.get_account_balances()
        tickers = self.tickers()
        snapshot_raw = {x[0]: x[3] for x in balances if (x[3]) > 0}
        snapshot = {x: self.floor(snapshot_raw[x], 4) for x in snapshot_raw if
                    self.to_amount(x, snapshot_raw[x], tickers) > 1.0}

        return snapshot

    def snapshot_total(self):
        tickers = self.tickers()
        snapshot = db.config(Const.SNAPSHOT, {})
        amounts = list((x, self.to_amount(x, snapshot[x], tickers)) for x in snapshot)
        amounts_str = [f'{x[0]} -> {x[1]}' for x in amounts]
        total = sum(x[1] for x in amounts)
        amounts_str.append("." * 15)
        amounts_str.append(f'Snapshot: {self.floor(total)}')
        msg = "\n".join(amounts_str)
        return msg

    def account_total(self):
        """
        Returns amounts and balances of the Symbols
        :return: Tuple( List(str, float),  List(str, float))
        """
        tickers = {x['symbol']: float(x['price'])
                   for x in self.client.get_all_tickers()}

        balances = self.get_account_balances()
        aggr_balances: Dict(str, float) = {x[0]: x[3] for x in balances if (x[3]) > 0}
        amounts: List[Tuple[str, float]] = list(filter(lambda x: x[1] > 0, ((x, self.to_amount(
            x, aggr_balances[x], tickers)) for x in aggr_balances)))
        return amounts, aggr_balances

    def price_alert(self, symbol, timeframe, count, threshold):
        # log.debug("getting price alert for : %s %s x %s", symbol, timeframe, count)
        # print(f'Symbol: {symbol}, timeframe: {timeframe} , count: {count}, threshold: {threshold}')
        klines = self.klines(symbol, timeframe, count)
        # Max and Min price in the klines
        # time, Open,High,Low,Close
        max_kline = max([(int(x[0]), float(x[2])) for x in klines], key=lambda y: y[1])
        min_kline = min([(int(x[0]), float(x[3])) for x in klines], key=lambda y: y[1])

        first_price = second_price = None
        if max_kline[0] < min_kline[0]:
            first_price = max_kline[1]
            second_price = min_kline[1]
        else:
            first_price = min_kline[1]
            second_price = max_kline[1]

        log.debug("Price Alert: %s, %s ->  %s", symbol, first_price, second_price)

        first_price = self.floor(first_price, 8)
        second_price = self.floor(second_price, 8)
        percentage = math.fabs(self.floor((first_price - second_price) * 100 / first_price, 1))
        current = self.floor(klines[-1][4], 8)

        key = f"{symbol}{timeframe}{count}{threshold}"
        curr_value = f"{first_price}{second_price}"
        existing_value = self.data[key] if key in self.data else ""

        if percentage > threshold:
            self.data[key] = curr_value
            if curr_value != existing_value:
                direction = '⬆' if first_price < second_price else '⬇'
                return f"{direction} {symbol:10} {percentage}% ({first_price}, {second_price}, {current}) "

    def stop_loss_orders_percentage(self):
        """Tuple(orderId, Symbol, StopPrice, CurrentPriceUSDT, Quantity, PercentageDiff)"""
        tickers = self.tickers()
        slOrders = self.get_open_orders(type='STOP_LOSS_LIMIT')

        stats = []
        for x in slOrders:
            # log.debug(x)
            currPrice = tickers[x['symbol']]
            stopPrice = float(x['price'])
            stopPriceUSDT = float(x['price']) * tickers['BTCUSDT'] if x['symbol'].endswith('BTC') else float(x['price'])
            qty = float(x['origQty'])
            prcGap = (currPrice - stopPrice) * 100 / currPrice
            currPriceUSDT = currPrice * tickers['BTCUSDT'] if 'BTC' in x['symbol'] else currPrice
            stats.append((x['orderId'], x['symbol'], stopPriceUSDT, currPriceUSDT, qty, round(prcGap, 2)))
        return stats

    def symbol_with_currency(self, symbol):
        return symbol.upper() + self.base_token(symbol.upper())

    def base_token(self, asset, token=None):
        cached_token = token if token else self.tickers()
        return 'USDT' if asset + 'USDT' in cached_token else 'BTC'

    def sell_x_percent(self, symbol='ALL', qty_prc=None, price_prc_over_market=0, test=True):
        if not qty_prc:
            raise Exception("X needs to be defined")
        if price_prc_over_market < 0:
            raise Exception("NEGATIVE VALUES NOT ALLOWED")

        tickers = self.tickers()
        balances = [(x[0], x[1]) for x in self.get_account_balances() if self.to_amount(x[0], x[1], tickers) > 100]
        sell_orders = [(x[0] + self.base_token(x[0], tickers), x[1] * qty_prc / 100,
                        tickers[x[0] + self.base_token(x[0], tickers)]) for x in balances if
                       x[0] != 'USDT' and symbol == 'ALL' or x[0] in symbol]
        log.debug(sell_orders)
        response = []
        for x in sell_orders:
            if float(x[2]) < 1 / (10 ** 4):
                log.warn('Ignoring a very low priced asset sell Order: %s %s', x[0], x[2])
                # continue
            orderObj = {'symbol': x[0],
                        'quantity': x[1],
                        'side': 'SELL',
                        'type': 'LIMIT',
                        'price': x[2] * (100 - 0.005 + price_prc_over_market) / 100,
                        'timeInForce': 'GTC'}
            currRes = self.place_order(orderObj, test=test)

            if 'BTC' in x[0]:
                # Convert to usdt price
                currRes['price'] = float(currRes['price']) * tickers['BTCUSDT']

            response.append(currRes)
        return response

    def buy_x_prc(self, symbol, prc_usdt, prc_belowmarket, test=True):
        if not prc_usdt:
            raise Exception("Percentage of USDT amount not defined")
        if prc_belowmarket < 0:
            raise Exception("Negative values not allowed")
        if not symbol:
            raise Exception("Symbol not defined")

        balances = list(filter(lambda x: x[0] == 'USDT', self.get_account_balances()))
        log.debug("USDT Balances: %s", balances)
        free_balance = balances[0][1] if len(balances) > 0 else 0

        buyAmount = min(prc_usdt * free_balance / 100, free_balance)

        tickers = self.tickers()
        eff_symbol = self.symbol_with_currency(symbol)
        qty = buyAmount / tickers[eff_symbol]
        buyPrice = tickers[eff_symbol] * (100 + 0.005 - prc_belowmarket) / 100
        orderObj = {'symbol': eff_symbol,
                    'quantity': qty,
                    'side': 'BUY',
                    'type': 'LIMIT',
                    'price': buyPrice,
                    'timeInForce': 'GTC'}
        currRes = self.place_order(orderObj, test=test)
        return currRes

    def get_open_orders(self, type=None, side=None):
        openOrders = self.client.get_open_orders(recvWindow=5000)
        # log.debug("open orders: %s", openOrders)
        if type:
            return list(filter(lambda x: x['type'] == type, openOrders))
        if side:
            return list(filter(lambda x: x['side'] == side, openOrders))

    def cancel_all_sl_orders(self, symbol='ALL'):
        stats = self.stop_loss_orders_percentage()
        # Cancel All Orders will high stop loss percentage
        cancelled = []
        for x in stats:
            if symbol=='ALL' or symbol in x[1]:
                log.debug("Cancelling SL order for : %s", x[1])
                self.client.cancel_order(symbol=x[1], orderId=str(x[0]))
                cancelled.append(x)
        # send the stats for cancelled orders
        return cancelled

    def revise_sl(self, symbol='ALL', threshold=4):
        stats = self.stop_loss_orders_percentage()
        log.info(f"Trying to revise Stop Loss for {threshold}%")

        # Cancel All Orders will high stop loss percentage
        cancelled_sl_symbols = []
        for x in filter(lambda x: (x[5] > (threshold + 0.25) and symbol == 'ALL' or symbol in x[1]), stats):
            self.client.cancel_order(symbol=x[1], orderId=str(x[0]))
            cancelled_sl_symbols.append(x[1])

        if len(cancelled_sl_symbols) > 0:
            log.info("trying to revise %s", cancelled_sl_symbols)
            resp = self.create_stop_loss_orders(test=False, stoploss_prc=threshold, symbols=cancelled_sl_symbols)
            return resp
        else:
            return []

    @staticmethod
    def dataframe(klines):
        klines_2d_array = [list(map(lambda x: float(x), x[1:6])) for x in klines]
        index_data = [app.timestamp_to_str(float(x[0]) / 1000) for x in klines]
        df = pd.DataFrame(np.array(klines_2d_array), index=index_data, columns=[
            'open', 'high', 'low', 'close', 'volume'])
        df.index = pd.to_datetime(df.index)
        return df


app = App()
