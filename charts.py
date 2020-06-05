# To add a new cell, type '# %%'
# To add a new markdown cell, type '# %% [markdown]'
import datetime
import math
import pathlib
import time
from typing import *

import matplotlib
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import plotext.plot as plx
from finta import TA

import log
from lib import app

theme = ['Solarize_Light2', 'fast', 'seaborn-bright'][2]
pathlib.Path('charts').mkdir(parents=True, exist_ok=True)
chart_tail_count = 100
ta_hints_bars = 4
figure_size = (11, 8)

class ChartHelper:
    def __init__(self):
        self.lowRsi = 30
        self.highRsi = 70
        self.hasBuyAppeared = False
        self.hasSellAppeared = False

    def polarity_shift_macd(self, x):
        if x[0] < 0 < x[-1]:
            return 1
        elif x[0] > 0 > x[-1]:
            return -1
        else:
            return 0

    def polarity_shift_rsi(self, x):
        val = 0
        if x < self.lowRsi and not self.hasBuyAppeared:
            self.hasBuyAppeared = True
            self.hasSellAppeared = False
            val = 1
        elif x > self.highRsi and not self.hasSellAppeared:
            self.hasSellAppeared = True
            self.hasBuyAppeared = False
            val = -1
        return val


def macd_x_over(df):
    macd = TA.MACD(df)
    methods = ChartHelper()
    macdCrossoverDF = (macd['MACD'] - macd['SIGNAL']).rolling(2).apply(methods.polarity_shift_macd, raw=True).shift(-1)
    crossoversSeriesGreen = macdCrossoverDF.loc[lambda x: x == 1]
    crossoversSeriesRed = macdCrossoverDF.loc[lambda x: x == -1]
    #
    crossoverDFGreen = macd.loc[crossoversSeriesGreen.index]['MACD']
    crossoverDFRed = macd.loc[crossoversSeriesRed.index]['MACD']
    lastGreen = crossoverDFGreen.index[-1]
    lastRed = crossoverDFRed.index[-1]

    buysell = "Buy" if lastGreen > lastRed else "Sell"
    lastTime: Timestamp = max(lastRed,lastGreen)
    seondsAgo = time.time()-lastTime.timestamp()
    hoursAgo = int(seondsAgo / 60 / 60)
    signal_info =  f"{buysell} at {lastTime}, {hoursAgo} hours ago"

    def plottable(ax):
        if ax:
            macd.tail(chart_tail_count).plot(figsize=figure_size, ax=ax)
            try:
                ax.scatter(crossoverDFGreen.index[-1], crossoverDFGreen.values[-1], s=100, c='green')
                ax.scatter(crossoverDFRed.index[-1], crossoverDFRed.values[-1], s=100, c='red')
            except Exception as e1:
                log.exception(e1)

    return {'signal' : buysell, 'time': lastTime, 'info': signal_info, 'plot': plottable}

def rsi(df):
    methods = ChartHelper()
    rsi = TA.RSI(df)
    lastRSI = app.floor(sum(rsi.tail(3).values) / 3, 1)

    def plottable(ax):
        if ax:
            stock_rsi = TA.STOCHRSI(df).multiply(100)
            rsiPoints = rsi.tail(rsi.shape[0] - 10).apply(methods.polarity_shift_rsi)
            rsiPointsGreen = rsiPoints.where(lambda x: x == 1).shift(0).dropna().tail(2)
            rsiPointsRed = rsiPoints.where(lambda x: x == -1).shift(0).dropna().tail(2)
            pd.concat([rsi, stock_rsi], axis=1).tail(chart_tail_count).plot(figsize=figure_size, ax=ax)
            try:
                if rsiPointsRed.shape[0] > 0:
                    ax.scatter(rsiPointsRed.index, rsi[rsiPointsRed.index].values, s=100, c='red')
                if rsiPointsGreen.shape[0] > 0:
                    ax.scatter(rsiPointsGreen.index, rsi[rsiPointsGreen.index].values, s=100, c='green')
            except Exception as e1:
                log.exception(e1)

    signal = 'Buy' if lastRSI < 35 else 'WAIT'
    return {'signal' : signal , 'info': f'RSI: {lastRSI}', 'plot': plottable}

def bb(df):
    bands = TA.BBANDS(df).tail(chart_tail_count)
    close_tailed = df['close'].tail(chart_tail_count)

    def plottable(ax):
        if ax:
            bands['Close'] = close_tailed
            bands.plot(ax=ax)

    bands_ta = bands.tail(ta_hints_bars)
    close_ta_hints = df['close'].tail(ta_hints_bars)
    bb_diff = ((close_ta_hints - bands_ta['BB_LOWER'])*100/bands_ta['BB_LOWER'])
    bb_min_dist , bb_max_dist= min(bb_diff.values), max(bb_diff.values)
    info = f"BB min-max: {app.floor_new(bb_min_dist)} - {app.floor_new(bb_max_dist)}"
    signal = 'Buy' if bb_min_dist < 3 and bb_max_dist < 5 else 'WAIT'
    return {'signal' : signal , 'info':info, 'plot': plottable}

def ta(asset, timeframe, count, fig, ax):
    methods = ChartHelper()
    matplotlib.use('agg')
    matplotlib.pyplot.switch_backend('Agg')
    plt.style.use(theme)
    signal = f"{asset} {timeframe} ->"
    # https://github.com/matplotlib/matplotlib/issues/14304

    klines = app.klines(asset, timeframe, count)
    df = app.dataframe(klines)

    if ax[0]:
        close = df['close']
        ema50 = TA.EMA(df, period=50)
        vwma = TA.EVWMA(df)
        pd.concat([close, ema50, vwma], axis=1).tail(chart_tail_count).plot(ax=ax[0], figsize=figure_size)

    macd_resp = macd_x_over(df)
    buysell , lastTime = macd_resp['signal'], macd_resp['time']
    hoursAgo = int((time.time()-lastTime.timestamp()) / 60 / 60)
    signal = signal + f"\n {buysell}: at {lastTime}, {hoursAgo} hours ago"
    if ax[1]:
        macd_resp['plot'](ax[1])

    rsi_resp = rsi(df)
    signal = signal + f"\n {rsi_resp['signal']}: {rsi_resp['info']}"
    if ax[2]:
        rsi_resp['plot'](ax[2])

    # Prepare TA Hints
    # - SMA50
    sma = TA.SMA(df, period=20 if timeframe == '1d' else 50)
    current_ma_20 = app.floor(sum(sma.tail(1).values), 9)
    current_price = float(klines[-1][4])
    prc_from_ema20 = app.floor_new((current_price - current_ma_20) * 100 / current_ma_20, 2)
    signal = signal + f"\n Price ovr SMA: {prc_from_ema20} "
    # min, max Bollinger lower band distance in last 4 bars

    # kama = TA.KAMA(df) # KAMA instead of SMA
    # , MA=kama
    bb_resp = bb(df)
    if ax[3]:
        bb_resp['plot'](ax[3])
    signal = signal + f"\n {bb_resp['signal']}: {bb_resp['info']}"

    # Average Directional Movement, Directional Movement Indicator
    adx = TA.ADX(df).tail(ta_hints_bars)
    dmi = TA.DMI(df).tail(ta_hints_bars)
    direction = "Buy" if (dmi['DI+'][-1] > dmi['DI-'][-1]) else "Sell"
    adxStr = getAdxIntensity(adx.values[-1])
    signal = signal + f"\n ADX/DMI: {adxStr} {direction}"
    return signal

def getAdxIntensity(adx):
    if adx < 30:
        return "Weak"
    elif adx > 30 and adx < 50:
        return "Strong"
    else:
        return "Very Strong"


def candles(asset, timeframe, count) -> Tuple[str, str]:
    methods = ChartHelper()
    log.debug("charting: %s : %s x %s", asset, timeframe, count)
    matplotlib.use('agg')
    matplotlib.pyplot.switch_backend('Agg')
    plt.style.use(theme)
    # https://github.com/matplotlib/matplotlib/issues/14304

    klines = app.klines(asset, timeframe, count)
    df = app.dataframe(klines)
    df.columns = [c[0].upper() + c[1:] for c in df.columns]
    mpf.plot(df, type='candle', figscale=2)
    fig = plt.gcf()
    filename = 'charts/' + asset + "_candled_" + str(int(round(time.time() * 1000))) + '.png'
    fig.savefig(filename)

    plx.plot(range(0, len(klines)), [float(x[4]) for x in klines], rows=25, cols=90)
    plx.show()

    return filename, "\n".join(identify_candles(klines))


def identify_candles(klines: List[Tuple[str, str, str, str, str]]):
    msgs = []
    for x in klines:
        t, o, h, l, c = datetime.datetime.fromtimestamp(float(x[0]) / 1000), float(x[1]), float(x[2]), float(
            x[3]), float(x[4])
        length = h - l
        thickness = math.fabs(o - c)
        if ((h - l) > 3 * math.fabs(o - c)) and ((h - l) > 0.8 * (h - l)) and ((o - l) > 0.8 * (h - l)):
            msgs.insert(0, f"DragonFly Doji at: {t}")
    return msgs[0:2]


def balance_pie():
    matplotlib.use('agg')
    matplotlib.pyplot.switch_backend('Agg')
    plt.style.use(theme)
    balances = app.account_total()[0]
    total = sum([x[1] for x in balances])
    filtered_balances = list(filter(lambda x: x[1] > 10, balances))
    labels = [x[0] + "\n" + app.floor_new(x[1], 1) for x in filtered_balances]
    sizes = [int(x[1] * 100 / total) for x in filtered_balances]

    fig, ax1 = plt.subplots(1)
    ax1.pie(sizes, labels=labels, startangle=90, autopct='%1.1f%%')
    ax1.axis('equal')
    plt.draw()
    filename = 'charts/balance)' + str(int(round(time.time() * 1000))) + '.png'
    pathlib.Path('charts').mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    fig.savefig(filename)
    return filename, app.floor(total, 1)

def balance_chart(balances):
    matplotlib.use('agg')
    matplotlib.pyplot.switch_backend('Agg')
    plt.style.use(theme)
    fig, ax1 = plt.subplots(1)
    ax1.plot(range(0,len(balances)),balances)
    plt.draw()

    try:
        plx.plot(range(0,len(balances)),balances, rows=25, cols=90)
        plx.show()
    except:
        pass

    filename = 'charts/balance)' + str(int(round(time.time() * 1000))) + '.png'
    pathlib.Path('charts').mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    fig.savefig(filename)
    return filename