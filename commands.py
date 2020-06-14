import logging
import os
import threading
import time
from typing import *

import matplotlib.pyplot as plt
import schedule
from dotmap import DotMap

import charts
import log
import processor
from access import accessControl
from db import db, Const
from lib import app

accessdenied = 'accessdenied'

_macd_data = DotMap()

def check_loggers():
    for h in log.handlers:
        log.info(h)

    for h in logging.getLogger().handlers:
        log.info(h)


def wrapper(fn):
    def wrapped(task):
        current_name = threading.current_thread().getName()
        if 'ThreadPool' in current_name:
            threading.current_thread().setName('Command_' + current_name[-3:])

        start = time.time_ns()
        try:
            msg = fn(task)
            if msg and len(msg) > 0 and task.message.chat.id:
                if not isinstance(task.message.chat.id, int) \
                        or ( isinstance(task.message.chat.id, str) and not task.message.chat.id.isnumeric()):
                    log.warn("Please set the adminChatID");
                else:
                    app.send_msg(msg, task.message.chat.id)
                    if task.message.source == 'terminal':
                        log.info("\n%s", msg)
            elif task.message.chat.id:
                pass
                # app.notify_action(task.message.chat.id)
        except Exception as e:
            log.exception(e)
        end = time.time_ns()
        log.debug("time taken for %s : %s ms", fn.__name__, app.floor((end - start) / 1000 / 1000, 2))

    return wrapped


def identity(x):
    return x


def overlap(source, target, types, functions=None):
    for x in enumerate(source):
        index, value = x
        fn = functions[index] if functions and len(functions) > index and functions[index] else identity
        target[index] = fn(types[index](value))
    return target


@wrapper
def cm_echo(task):
    return 'Alive!'


def util_balance_hash(balances: Dict[str, float]):
    sorted_keys = sorted(balances.keys())
    return "".join([x + str(app.floor(balances[x], 3)) for x in sorted_keys if balances[x] > 0.005])


@wrapper
def cm_bal(task):
    amounts, balances = app.account_total()
    previous_amounts = db.config(Const.BALANCE, {})
    previous_bal_hash = db.config(Const.BALANCE_HASH, "")

    total = app.floor(sum(x[1] for x in amounts), 2)
    if task.params and len(task.params) > 0 and task.params[0] == 'short':
        return f"Balance: {total}"

    account_bal_hash = util_balance_hash(balances)
    is_hash_matching = account_bal_hash == previous_bal_hash
    msg_lines = []
    for x in amounts:
        prc_diff = app.floor((x[1] - previous_amounts[x[0]]) * 100 / previous_amounts[x[0]]) \
            if x[0] in previous_amounts else 'NA'
        bal_str = f'{x[0]} -> {x[1]} ({prc_diff})' if is_hash_matching else f'{x[0]} -> {x[1]}'
        if x[1] > 10:
            msg_lines.append(bal_str)
    msg_lines.append("." * 15)
    msg_lines.append(f'Total: {total}')
    msg = "\n".join(msg_lines)

    if not is_hash_matching:
        db.set_config(Const.BALANCE, {x[0]: x[1] for x in amounts})
        db.set_config(Const.BALANCE_HASH, account_bal_hash)
        log.info("saved new balances!")

    return msg


@wrapper
def cm_bye(task):
    print("Exiting.. Bye!")
    os._exit(0)


@wrapper
def cm_revise_sl(task):
    params = overlap(task.params, ['ALL', 4], [str, float], [str.upper])
    resp = app.revise_sl(*params)
    return f'new sl orders:{len(resp)}'


@wrapper
def cm_create_sl(task):
    params = overlap(task.params, ['ALL', 4], [str, float], [str.upper])
    if params[0] == 'ALL':
        free_balances = app.get_free_balances_non_usdt()
        symbols = [x[0].upper() for x in free_balances]
    else:
        symbols = [app.symbol_with_currency(params[0])]

    resp = app.create_stop_loss_orders(symbols=symbols, test=False, stoploss_prc=params[1])
    return f'new sl orders:{len(resp)}' if len(resp) > 0 else None


@wrapper
def cm_price_alerts(task):
    params = overlap(task.params, ['5m', 6, 0], [str, int, float])
    messages = []

    tickers = app.tickers()
    for x in db.config(Const.SYMBOLS, []):
        base_currency = 'USDT' if f'{x}USDT' in tickers else 'BTC'
        symbol = x + base_currency
        msg = app.price_alert(symbol=symbol, timeframe=params[0], count=int(params[1]), threshold=float(params[2]))
        if msg:
            messages.append(msg)

    if len(messages) > 0:
        up = list(filter(lambda y: y[0] == '⬆', messages))
        down = list(filter(lambda y: y[0] != '⬆', messages))

        up.append('- ' * 10)
        up.extend(down)

        return "\n".join(up)


@wrapper
def cm_current_prices(task):
    tickers = app.tickers()
    msg = ""
    for x in db.config(Const.SYMBOLS, []):
        symbol = app.symbol_with_currency(x)
        price = tickers[symbol]
        price_USDT = price if 'USDT' in symbol else price * tickers['BTCUSDT']
        msg += f"{symbol}: {app.floor(price_USDT, 4)}, \n"
    return msg


@wrapper
def cm_add_symbols(task):
    symbols = set(db.config(Const.SYMBOLS, ['ADA']))

    for x in list(task.params):
        log.debug("adding symbol %s", x)
        symbols.add(x.upper())

    db.set_config(Const.SYMBOLS, list(symbols))


@wrapper
def cm_rm_symbols(task):
    symbols = set(db.config(Const.SYMBOLS, []))

    for x in list(task.params):
        log.debug("removing symbol %s", x)
        symbols.discard(x.upper())

    db.set_config(Const.SYMBOLS, list(symbols))


@wrapper
def cm_stop_loss_info(task):
    stats = app.stop_loss_orders_percentage()
    msg = []
    total = 0
    for x in stats:
        price = app.floor(x[2] * x[4], 2)
        msg.append(f'{x[1]} -> {price} , {app.floor(x[5])}%')
        total += price
    if len(msg) > 0:
        msg.append('-' * 15)
        msg.append(f'Stoploss Total -> {app.floor(total, 2)}')
        return "\n".join(msg)
    else:
        return "No Stoploss Orders Found!"


@wrapper
def cm_cancel_sl(task):
    symbol = task.params[0].upper() if task.params and len(task.params) > 0 else 'ALL'
    log.debug("Cancelling Stop Losses for Symbol: %s ", symbol)
    stats = app.cancel_all_sl_orders(symbol=symbol)
    return f'cancelled {len(stats)} Stop Loss Orders'


@wrapper
def cm_order_sell_cancel(task):
    symbol = task.params[0].upper() if task.params and len(task.params) > 0 else 'ALL'
    orders = app.get_open_orders(side='SELL')
    cancelled = []
    for x in orders:
        if symbol == 'ALL' or symbol in x['symbol']:
            log.info("Cancelling Sell order for : %s", x['symbol'])
            app.client.cancel_order(symbol=x['symbol'], orderId=str(x['orderId']))
            cancelled.append(x)
    return f"{len(cancelled)} Sell Orders Cancelled"


@wrapper
def cm_order_buy_cancel(task):
    symbol = task.params[0].upper() if task.params and len(task.params) > 0 else 'ALL'
    orders = app.get_open_orders(side='BUY')
    cancelled = []
    for x in orders:
        if symbol == 'ALL' or symbol in x['symbol']:
            log.info("Cancelling Buy order for : %s", x['symbol'])
            app.client.cancel_order(symbol=x['symbol'], orderId=str(x['orderId']))
            cancelled.append(x)
    return f"{len(cancelled)} Buy Orders Cancelled"


@wrapper
def cm_sell_x_prc(task):
    params = overlap(task.params, ['ALL', None, 0], [str, float, float], [str.upper])
    return sell_x_prc_internal(params[0], params[1], params[2], test=False)


@wrapper
def cm_buy_x_prc_test(task):
    params = overlap(task.params, [None, None, 0], [str, float, float], [str.upper])
    order = app.buy_x_prc(params[0], params[1], params[2], test=True)
    total = app.floor_new(float(order['quantity']) * float(order['price']), 2)
    return f"Test Buy Order Placed: {order['symbol']}, price:{order['price']}, total: {total}"


@wrapper
def cm_buy_x_prc(task):
    params = overlap(task.params, [None, None, 0], [str, float, float], [str.upper])
    order = app.buy_x_prc(params[0], params[1], params[2], test=False)
    total = app.floor_new(float(order['quantity']) * float(order['price']), 2)
    return f"Buy Order Placed: {order['symbol']}, price:{order['price']}, total: {total}"


@wrapper
def cm_sell_x_prc_test(task):
    params = overlap(task.params, ['ALL', None, 0], [str, float, float], [str.upper])
    return sell_x_prc_internal(params[0], params[1], params[2], test=True)


def sell_x_prc_internal(symbol, quantity, priceOverMarket, test=True):
    log.debug(f'attempting for {quantity}, {priceOverMarket}')
    response = app.sell_x_percent(symbol, quantity, priceOverMarket, test)
    log.debug(response)
    msgs = [f'{x["symbol"]} -> {app.floor(float(x["quantity"]) * float(x["price"]), 2)}' for x in response]
    msgs.append('.' * 15)
    total = app.floor(sum([float(x["quantity"]) * float(x["price"]) for x in response]), 2)
    msgs.append(f'Sell Total : {total}')
    test_str = "Test " if test else ""
    msg = '\n'.join([f' {test_str}Sell Orders Placed'] + msgs)
    return msg


@wrapper
def cm_save_snapshot(task):
    snapshot = app.get_snapshot()
    db.set_config(Const.SNAPSHOT, snapshot)

    snapshot_str = ['Snapshot'] + [f'{x} -> {snapshot[x]}' for x in snapshot]
    msg = "\n".join(snapshot_str)
    return msg


@wrapper
def cm_snapshot_total(task):
    return app.snapshot_total()


@wrapper
def cm_ta(task):
    task.params = overlap(task.params, [None, '1h', 1000], [str, str, int], [app.symbol_with_currency])
    return create_chart_internal(task, chart='ta', draw=True)


@wrapper
def cm_ta_hints(task):
    task.params = overlap(task.params, [None, '1h', 1000], [str, str, int], [app.symbol_with_currency])
    return create_chart_internal(task, chart='ta', draw=False)


@wrapper
def cm_candles(task):
    task.params = overlap(task.params, [None, '15m', 50], [str, str, int], [app.symbol_with_currency])
    return create_chart_internal(task, chart='candles', draw=True)


def create_chart_internal(task, chart='ta', draw=True):
    params = task.params
    log.debug("charting: %s", params)
    if not params[0]:
        raise Exception("The Asset name is needed")
    asset = params[0]

    files = []
    signals = []
    msg1 = msg2 = msg3 = None
    if chart == 'ta':
        if params[1] == 'all':
            fig, ax = plt.subplots(3, 4) if draw else (
                None, [[None]*4]*3)
            msg1 = charts.ta(asset, '1h', params[2], fig, ax[0])
            msg2 = charts.ta(asset, '4h', params[2], fig, ax[1])
            msg3 = charts.ta(asset, '1d', params[2], fig, ax[2])
        else:
            fig, ax = plt.subplots(4) if draw else (None, [None]*4)
            msg1 = charts.ta(asset, params[1], params[2], fig, ax)

        if msg1:
            signals.append(msg1)
        if msg2:
            signals.append(msg2)
        if msg3:
            signals.append(msg3)

        if draw:
            filename = 'charts/' + asset + "_" + str(int(round(time.time() * 1000))) + '.png'
            fig.savefig(filename, dpi=300)
            files.append((filename, asset))

    elif chart == 'candles':
        if params[0] == 'ALLBTC' or params[0] == 'ALLUSDT':
            for symbol in db.config(Const.SYMBOLS):
                filename, msg = charts.candles(app.symbol_with_currency(symbol), params[1], params[2])
                files.append((filename, app.symbol_with_currency(symbol)))
        else:
            filename, msg = charts.candles(asset, params[1], params[2])
            files.append((filename, asset))

        if msg:
            signals.append(msg)

    for filename in files:
        app.send_photo(filename[0], caption=f'Chart: {filename[1]}, {params[1]} x {params[2]}',
                       chat_id=task.message.chat.id)
        os.remove(filename[0])

    return "\n".join(signals)


@wrapper
def cm_balance_pie(task):
    filename, total = charts.balance_pie()
    app.send_photo(filename, caption=f'Balance: {total}', chat_id=task.message.chat.id)
    os.remove(filename)

@wrapper
def cm_balance_chart(task):
    filename = charts.balance_chart(db.config('balcheckpoints',[]))
    app.send_photo(filename, caption=f'Balance Chart', chat_id=task.message.chat.id)
    os.remove(filename)

@wrapper
def cm_balance_checkpoint(task):
    amounts, balances = app.account_total()
    total = sum([x[1] for x in amounts])
    balances = db.config('balcheckpoints', [])
    while len(balances) > 500:
        balances.pop(0)
    balances.append(total)
    db.set_config('balcheckpoints', balances)

@wrapper
def cm_my_commands(task):
    author = task.message.chat.username.lower()
    messages = list(filter(lambda x: author == accessControl.adminUserId or (accessManagement[x] and author in accessManagement[x]),
                           accessManagement.keys()))
    messages.remove('accessdenied')
    messages.remove('mine')
    return "\n".join(messages)


@wrapper
def cm_schd(task):
    seconds = int(task.params[0])
    command_str = "/" + " ".join(task.params[1:])
    sub_command = task.params[1]

    new_message = DotMap(task.message.toDict())
    new_message.text = command_str
    new_message.scheduletag = time.time()
    # Avoid cyclic scheduled commands and the accessdenied ones
    log.info("trying to schedule: %s", command_str)
    if accessdenied not in command_str and 'schd' not in command_str and sub_command in commands:
        scheduled_obj = schedule \
            .every(seconds).seconds \
            .do(processor.process_message, new_message).tag(sub_command, 'all', new_message.scheduletag)
        log.info(scheduled_obj)


def cm_price_reach_condition(task, condition):
    symbol = app.symbol_with_currency(task.params[0])
    price = float(task.params[1])
    tickers = app.tickers()
    log.debug(f"Checking if Price is {condition} : {symbol} {price}")
    curr_price = tickers[symbol]
    test = curr_price > price if condition == 'above' else curr_price < price
    if test:
        log.info(f"target price reached: {symbol} {condition} {price}")
        command = task.params[2:]
        command_str = "/" + " ".join(command)
        new_message = DotMap(task.message.toDict())
        new_message.text = command_str
        processor.process_message(new_message)
        if task.message.scheduletag:
            log.info("clearing the schedule of Price Condition")
            schedule.clear(task.message.scheduletag)


@wrapper
def cm_is_price_above(task):
    return cm_price_reach_condition(task, 'above')


@wrapper
def cm_is_price_below(task):
    return cm_price_reach_condition(task, 'below')


@wrapper
def cm_clear_schedule(task):
    if len(task.params) == 0:
        return "missing tags for clearing schedules:\ncommand name | all"
    schedule.clear(task.params[0])


@wrapper
def cm_print_schd(task):
    msg = "\n".join([
        "Every " + str(x.interval) + " " + str(x.unit) + " " + x.job_func.args[0].text for x in
        schedule.jobs
    ])
    if msg and len(msg) > 0:
        return msg
    else:
        return "No Scheduled Tasks found!"


@wrapper
def cm_access_denied(task):
    return "access denied : " + " ".join(task.params)


@wrapper
def cm_macd_show(task):
    return "\n".join([f"{x} -> {_macd_data[x][0]} at {_macd_data[x][1]}" for x in _macd_data])


@wrapper
def cm_macd(task):
    params = overlap(task.params, [None, '1h', 1000], [str, str, int])
    log.debug(params)
    messages = []
    for symbol in params[0].split(","):
        symbol_with_currency = app.symbol_with_currency(symbol)
        df = app.dataframe(app.klines(symbol_with_currency, params[1], params[2]))
        key = f'{symbol_with_currency}{params[1]}'
        resp = charts.macd_x_over(df)
        signal, signal_time = resp['signal'], resp['time']
        old = _macd_data[key]
        if not old or ( old[0] != signal and old[1] < signal_time):
            _macd_data[key] = signal, signal_time
        messages.append(f"{symbol}: {signal} at {signal_time}")
    if len(messages) > 0:
        return "\n".join([f"{params[1]} -> "] + messages)

commands = {
    'echo': cm_echo,
    'bal': cm_bal,
    'bye': cm_bye,
    'sellcancel': cm_order_sell_cancel,
    'buycancel': cm_order_buy_cancel,
    'slrevise': cm_revise_sl,
    'slcreate': cm_create_sl,
    'slcancel': cm_cancel_sl,
    'slinfo': cm_stop_loss_info,
    'hot': cm_price_alerts,
    'now': cm_current_prices,
    'symboladd': cm_add_symbols,
    'symbolrm': cm_rm_symbols,
    'sellx': cm_sell_x_prc,
    'buyx': cm_buy_x_prc,
    'buyxtest': cm_buy_x_prc_test,
    'sellxtest': cm_sell_x_prc_test,
    'snapshot': cm_save_snapshot,
    'snapshotbal': cm_snapshot_total,
    'ta': cm_ta,
    'hints': cm_ta_hints,
    'candles': cm_candles,
    'schd': cm_schd,
    'schdcancel': cm_clear_schedule,
    'schdinfo': cm_print_schd,
    'balpie': cm_balance_pie,
    'balchart': cm_balance_chart,
    'balcheckpoint': cm_balance_checkpoint,
    'mine': cm_my_commands,
    'ifabove': cm_is_price_above,
    'ifbelow': cm_is_price_below,
    'accessdenied': cm_access_denied,
    'macd': cm_macd,
    'macdshow': cm_macd_show
}

examples = {
    'sellxtest': "10 .01",
    'hot': "1h 200 1",
    'symboladd': "ADA",
    'symbolrm': "ADA",
    'ta': "ADA 1h 300",
    'candles': "ADA 1h 300",
    'schd': "10 echo",
    'bal': "short",
    'bal': "save",
    "now": ""
}

# If a command is not specified below, which means it has access to only Admin `adminUserId`
publicMembers = accessControl.groups.public
privateMembers = accessControl.groups.private
accessManagement: Dict[str, List] = {
    'echo': publicMembers,
    'bal': privateMembers,
    'hot': publicMembers,
    'now': publicMembers,
    'slinfo': privateMembers,
    'sellxtest': privateMembers,
    'buyxtest': privateMembers,
    'snapshotbal': privateMembers,
    'ta': publicMembers,
    'hints': publicMembers,
    'candles': publicMembers,
    'mine': publicMembers,
    'accessdenied': publicMembers,
    'schd': privateMembers,
    'schdinfo': privateMembers
}


def run_command(command: str, params: List):
    task = DotMap()
    task.message.chat.id = accessControl.adminChatId
    task.params = params
    task.message.source = 'terminal'
    return commands[command](task)
