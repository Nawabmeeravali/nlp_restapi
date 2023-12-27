import uuid
import time
import datetime
from concurrent.futures import thread

import pyotp
import telebot
import yfinance as yf
from finta import TA
import pandas as pd
import numpy as np
import tracemalloc

from alphatrade import AlphaTrade, LiveFeedType, OrderType, ProductType, TransactionType


def log(message):
    print(message)
    bot.send_message(chat_id=CHATID, text=message)



PERIOD_ST = 10

MULTIPLIER_ST = 3

SUPER_TREND_HEAD = ['open', 'high', 'low', 'close', 'EMA_5']

YFINANCE_HEAD_CONTENT = ['open', 'high', 'low', 'close', 'Adj Close', 'volume']

CHATID = -1001980806118

PERIOD = '1mo'

TOTP = 'Q7UENEVLTWWXXFZN'

API_TOKEN = '6290258700:AAG_zFEGa42vXJbepXPOkA3QNOPHp38eNJU'
bot = telebot.TeleBot(API_TOKEN)

PIN = pyotp.TOTP(TOTP).now()
log(PIN)

PIN = pyotp.TOTP(TOTP).now()
totp = f"{int(PIN):06d}" if len(PIN) <= 5 else PIN
sas = AlphaTrade(login_id="SV294", password="MNawab@03", twofa=PIN)

TIMEFRAME = '60m'
BOXP = 5
BUFFER = 5
position = [False, False]
NIFTY = False
POSITIONS = [[], []]
BankNiftyBuy = False
BankNiftySell = False
LTP = 0
expiry_date = datetime.date(2023, 5, 25)
today_date = datetime.datetime.now()
next_expiry_date = datetime.date(2021, 5, 6)

def get_latest_nifty_future(symbol):
    matched_item_list = []
    nifty_future = None
    search_result = sas.search_instruments("NFO", symbol)
    today_month = today_date.month
    today_day = today_date.day
    for i in search_result:
        if 'FUT' in i.symbol and i.symbol.startswith(symbol):
            matched_item_list.append(i)
    print(matched_item_list)
    for i in reversed(matched_item_list):
        if i.expiry.month == today_month:
            log("PickedFuture : {}  | todayDate : {}  | expiryDate : {} | expiryMonth : {} ".format(i.symbol,str(today_date),str(i.expiry.day),str(i.expiry.month)))

            if i.expiry.day > today_day:
                nifty_future = i
            else:
                today_month = today_month + 1
                today_day = 1

    return nifty_future

banknifty_future = get_latest_nifty_future('BANKNIFTY')

log("Script Start Time :: " + str(datetime.datetime.now()))





def super_trend(dataframe, name, period=PERIOD_ST, multiplier=MULTIPLIER_ST, ohlc=SUPER_TREND_HEAD):
    # small variation from jignesh patel super trend indicator
    atr = 'ATR_' + str(period)
    st = 'ST' + name  # + str(period) + '_' + str(multiplier)
    stx = 'STX' + name  # + str(period) + '_' + str(multiplier)

    # Compute basic upper and lower bands
    dataframe['basic_ub'] = (dataframe[ohlc[4]]) + multiplier * dataframe[atr]
    dataframe['basic_lb'] = (dataframe[ohlc[4]]) - multiplier * dataframe[atr]

    # Compute final upper and lower bands
    dataframe['final_ub'] = 0.00
    dataframe['final_lb'] = 0.00
    for i in range(period, len(dataframe)):
        dataframe['final_ub'].iat[i] = max(dataframe['basic_ub'].iat[i - 1], dataframe['basic_ub'].iat[i]) if \
            dataframe['basic_ub'].iat[i] < \
            dataframe['final_ub'].iat[i - 1] or \
            dataframe[ohlc[4]].iat[i - 1] > \
            dataframe['final_ub'].iat[i - 1] else \
            dataframe['final_ub'].iat[i - 1]
        dataframe['final_lb'].iat[i] = min(dataframe['basic_lb'].iat[i - 1], dataframe['basic_lb'].iat[i]) if \
            dataframe['basic_lb'].iat[i] > \
            dataframe['final_lb'].iat[i - 1] or \
            dataframe[ohlc[4]].iat[i - 1] < \
            dataframe['final_lb'].iat[i - 1] else \
            dataframe['final_lb'].iat[i - 1]

    # Set the Super-trend value
    dataframe[st] = 0.00
    for i in range(period, len(dataframe)):
        if dataframe[st].iat[i - 1] == dataframe['final_ub'].iat[i - 1] and dataframe[ohlc[3]].iat[i] <= \
                dataframe['final_ub'].iat[i]:
            dataframe[st].iat[i] = dataframe['final_ub'].iat[i]
        elif dataframe[st].iat[i - 1] == dataframe['final_ub'].iat[i - 1] and dataframe[ohlc[3]].iat[i] > \
                dataframe['final_ub'].iat[i]:
            dataframe[st].iat[i] = dataframe['final_lb'].iat[i]
        elif dataframe[st].iat[i - 1] == dataframe['final_lb'].iat[i - 1] and dataframe[ohlc[3]].iat[i] < \
                dataframe['final_lb'].iat[i]:
            dataframe[st].iat[i] = dataframe['final_ub'].iat[i]
        else:
            dataframe[st].iat[i] = 0.0

        # Mark the trend direction up/down
    dataframe[stx] = np.where((dataframe[st] > 0.00), np.where((dataframe[ohlc[3]] < dataframe[st]), 'down', 'up'),
                              np.NaN)

    # Remove basic and final bands from the columns
    dataframe.drop(['basic_ub', 'basic_lb', 'final_ub', 'final_lb'], inplace=True, axis=1)

    dataframe.fillna(0, inplace=True)
    return dataframe


def set_stuff(x):
    x[0] = 1
    a = []
    for idx, val in enumerate(x):
        if val == 0.0:
            y = a[-1]
            a.append(y)
        else:
            a.append(val)
    return np.array(a)

def moveByOne(x):
    return x.shift(periods=5)


def get_data(symbol):
    # symbol = '^NSEI'
    data_frame = yf.download(symbol, period=PERIOD, interval=TIMEFRAME)
    data_frame.columns = YFINANCE_HEAD_CONTENT
    data_frame.reset_index(inplace=True)

    data_frame['ll'] = data_frame['low'].rolling(window=BOXP).min()
    data_frame['k1'] = data_frame['high'].rolling(window=BOXP).max()
    data_frame['box1'] = np.greater(data_frame['high'].rolling(window=BOXP - 1).max(),
                                    data_frame['high'].rolling(window=BOXP - 2).max())

    # dropping adjusted close as we don't use it
    data_frame.drop(['Adj Close'], inplace=True, axis=1)

    # data_frame populate 10 and 15 period ATR needed for super trend
    data_frame = pd.concat([data_frame, TA.ATR(data_frame, 10)], axis=1)
    data_frame = pd.concat([data_frame, TA.ATR(data_frame, 5)], axis=1)
    data_frame.rename(columns={"10 period ATR": 'ATR_' + str(10)}, inplace=True)
    data_frame.rename(columns={"5 period ATR": 'ATR_' + str(5)}, inplace=True)

    # data_frame populate 5 period EMA needed for super trend
    data_frame = pd.concat([data_frame, TA.EMA(data_frame, 5)], axis=1)
    data_frame.rename(columns={"5 period EMA": 'EMA_' + str(5)}, inplace=True)

    # data_frame populate parabolic SAR
    data_frame = pd.concat([data_frame, TA.PSAR(data_frame)], axis=1)
    data_frame.rename(columns={0: 'psar'}, inplace=True)

    # data_frame populate super trend data
    data_frame = super_trend(data_frame, 's')
    data_frame = super_trend(data_frame, 'f', 5, 1)

    data_frame["l_high"] = data_frame["high"].rolling(BOXP - 1).apply(lambda x: x[0], raw=True)
    data_frame["l_k1"] = data_frame["k1"].rolling(BOXP).apply(lambda x: x[0], raw=True)
    data_frame['topbox'] = set_stuff(
        np.where(np.logical_and(data_frame["l_high"] > data_frame["l_k1"], data_frame['box1']), data_frame["l_high"],
                 0))
    data_frame['bottombox'] = set_stuff(
        np.where(np.logical_and(data_frame["l_high"] > data_frame["l_k1"], data_frame['box1']), data_frame["ll"], 0))
    data_frame.drop(["l_high", "l_k1", 'k1', 'box1', 'll'], inplace=True, axis=1)
    return data_frame

def get_data_new(symbol):
    # symbol = '^NSEI'
    data_frame = yf.download(symbol, period=PERIOD, interval=TIMEFRAME)
    data_frame.columns = YFINANCE_HEAD_CONTENT
    data_frame.reset_index(inplace=True)

    data_frame['sup'] =  moveByOne(data_frame['low'].rolling(window=BOXP).min())
    data_frame['res'] = moveByOne(data_frame['high'].rolling(window=BOXP).max())
    data_frame = pd.concat([data_frame, TA.PSAR(data_frame)], axis=1)

    """data_frame['bullish'] =0.0
    data_frame['bullish'] = np.where(data_frame['close']> data_frame['tsl'],1.0,0.0)
    data_frame['crossover'] = data_frame['bullish'].diff()"""
    data_frame['f'] = np.where((data_frame['close'] > 0.00), np.where((data_frame['Adj Close'] < data_frame['psar']), 'down', 'up'),np.NaN)

    data_frame['signal'] = np.where(data_frame['f'] == 'up' , 1,
                                    np.where(data_frame['f'] == 'down', -1, 0))
    data_frame['signal'] = data_frame['signal']
    data_frame['tsl'] = np.where(data_frame['signal'] == 1, data_frame['res'], data_frame['sup'])
    data_frame['tsl'] = data_frame['tsl']

    data_frame['signal_test'] = np.where((data_frame['close'] > 0.00), np.where((data_frame['Adj Close'] < data_frame['tsl']), 'down', 'up'),np.NaN)



    # dropping adjusted close as we don't use it
    data_frame.drop(['Adj Close'], inplace=True, axis=1)
    data_frame.drop(['sup'], inplace=True, axis=1)
    data_frame.drop(['res'], inplace=True, axis=1)




    return data_frame

# (^NSEI)^NSEBANK

def buy_zerbra():
    global LTP
    x = int(LTP / 100) * 100
    global POSITIONS
    global NIFTY
    if NIFTY:
        symbol = 'NIFTY'
        val = 300
        q = 75
    else:
        symbol = 'BANKNIFTY'
        val = 700
        q = 25
    deep_call = sas.get_instrument_for_fno(symbol=symbol, expiry_date=expiry_date, is_fut=False, strike=x - val,
                                           is_call=True)
    atm_call = sas.get_instrument_for_fno(symbol=symbol, expiry_date=expiry_date, is_fut=False, strike=x, is_call=True)
    y = (deep_call, atm_call)
    if NIFTY:
        POSITIONS[0].append(y)
    else:
        POSITIONS[1].append(y)
    buy_signal(deep_call, 2 * q)
    sell_signal(atm_call, q)


def square_off(x):
    global POSITIONS
    p = POSITIONS
    log("squaring off positions")
    if x:
        for i in p[0]:
            buy_signal(i[1], 75)
            sell_signal(i[0], 2 * 75)
            POSITIONS[0].remove(i)

    else:
        for i in p[1]:
            buy_signal(i[1], 25)
            sell_signal(i[0], 50)
            POSITIONS[1].remove(i)



def buy_signal(ins_scrip, q):
    try:
        global sas
        order = sas.place_order(transaction_type=TransactionType.Buy,
                            instrument=ins_scrip,
                            quantity=q,
                            order_type=OrderType.Market,
                            product_type=ProductType.Delivery,
                            price=0.0,
                            trigger_price=0.0,
                            stop_loss=None,
                            square_off=None,
                            trailing_sl=None,
                            is_amo=False)
        if (None != order):
            message = "{} : {} | {} : {} | {} : {} | {} : {}".format("message", "BUY signal", "script", ins_scrip[2],
                                                                     "order", str(order), "status",
                                                                     order['status'] == 'success')
            log(message)
        print("buy", ins_scrip[2],order)
    except Exception as e:
        print("An exception occurred",e)

    print("buy", ins_scrip[2])


def sell_signal(ins_scrip, q):
    global sas
    try:
        order = sas.place_order(transaction_type=TransactionType.Sell,
                        instrument=ins_scrip,
                        quantity=q,
                        order_type=OrderType.Market,
                        product_type=ProductType.Intraday,
                        price=0.0,
                        trigger_price=0.0,
                        stop_loss=None,
                        square_off=None,
                        trailing_sl=None,
                        is_amo=False)
        if(None != order):
            message = "{} : {} | {} : {} | {} : {} | {} : {}".format("message","SELL signal","script",ins_scrip[2],"order",str(order),"status" , order['status'] == 'success')
            log(message)
        print("sell", ins_scrip[2],order)
    except Exception as e:
        print("An exception occurred", e)
    print("sell", ins_scrip[2])


def dravs_trading_strategy(ohlc):
    buy, sell = False, False
    global position
    global LTP
    global NIFTY
    LTP = ohlc['close'].values[-1]
    topbox, bottombox = ohlc['topbox'].values[-1] + BUFFER, ohlc['bottombox'].values[-1] - BUFFER
    message = '{}="{}" | {}="{}" | {}="{}"  | {}="{}" | {}="{}" | {}="{}"'.format("Message", "Inside Trading strategy",
                                                                                  "TOPBOX", topbox, "BOTTOMBOX",
                                                                                  bottombox, "close",
                                                                                  ohlc['close'].values[-1],
                                                                                  "previous_close",
                                                                                  ohlc['close'].values[-3],
                                                                                  "super_trend",
                                                                                  ohlc['STXs'].values[-1])
    log(message)
    if ohlc['close'].values[-1] > topbox and ohlc['close'].values[-3] < topbox:
        buy = True
    if ohlc['close'].values[-1] < bottombox and ohlc['close'].values[-3] > bottombox:
        sell = True
    if ohlc['STXs'].values[-1] == 'up' and buy and (
            (NIFTY is True and position[0] is False) or (NIFTY is False and position[1] is False)):
        if NIFTY:
            position[0] = True
        else:
            position[1] = True
        buy_zerbra()
        log('buy logic')
    if ohlc['STXs'].values[-1] == 'down' and sell:
        log('sell logic')
    if ohlc['STXf'].values[-1] == 'up' and ohlc['STXf'].values[-3] == 'down':
        log('stop sell')
    if ((ohlc['STXs'].values[-1] == 'down' and ohlc['STXs'].values[-3] == 'up') or ohlc["psar"].values[-1] >
        ohlc["close"].values[-1]) and ((NIFTY is True and position[0] is True) or (NIFTY is False and position[1])):
        if NIFTY:
            square_off(NIFTY)
            position[0] = False
        else:
            square_off(False)
            position[1] = False

        log('stop buy')
    print(topbox, bottombox)

def supertrend_trading_strategy(ohlc):
    global position
    global LTP
    global NIFTY
    LTP = ohlc['close'].values[-1]
    topbox, bottombox = ohlc['topbox'].values[-1] + BUFFER, ohlc['bottombox'].values[-1] - BUFFER
    message = '{}="{}" | {}="{}" | {}="{}"  | {}="{}" | {}="{}" | {}="{}"'.format("Message", "superTrend Trading strategy",
                                                                                  "TOPBOX", topbox, "BOTTOMBOX",
                                                                                  bottombox, "close",
                                                                                  ohlc['close'].values[-1],
                                                                                  "previous_close",
                                                                                  ohlc['close'].values[-3],
                                                                                  "super_trend",
                                                                                  ohlc['STXs'].values[-1])
    log(message)

    if ohlc['STXs'].values[-1] == 'up' and ohlc['STXs'].values[-3]  == 'down' and (
            (NIFTY is True and position[0] is False) or (NIFTY is False and position[1] is False)):
        log('buy logic')
    if ohlc['STXs'].values[-1] == 'down' and ohlc['STXs'].values[-3]  == 'up' :
        log('sell logic')

def psar_trading_strategy(ohlc,banknifty_future):
    global position
    global LTP
    global NIFTY
    global BankNiftyBuy
    global BankNiftySell
    LTP = ohlc['close'].values[-1]
    topbox, signaltest = ohlc['psar'].values[-1], ohlc['signal_test'].values[-1]
    message = '{}="{}" | {}="{}" | {}="{}"  | {}="{}" | {}="{}" | {}="{}" '.format("Message",
                                                                                  "psar Trading strategy",
                                                                                  "psar", topbox, "signal",
                                                                                  signaltest, "close",
                                                                                  ohlc['close'].values[-1],
                                                                                  "BankNiftyBuy",
                                                                                  BankNiftyBuy,"BankNiftySell",BankNiftySell,
                                                                                  )
    log(message)

    if ohlc['signal_test'].values[-1] == 'up' and ohlc['signal_test'].values[-2] == 'down' and BankNiftyBuy == False:
        multi = 1
        if (BankNiftySell):
            multi = 2
        BankNiftyBuy = True
        BankNiftySell = False
        log('buy logic')
        buy_signal(multi * 15)
    if ohlc['signal_test'].values[-1] == 'down' and ohlc['signal_test'].values[-2] == 'up' and BankNiftySell == False:
        multi = 1
        if(BankNiftyBuy):
            multi = 2

        BankNiftySell = True
        BankNiftyBuy = False
        log('sell logic')
        sell_signal(multi * 15)

    del ohlc


def run():
    global POSITIONS
    global NIFTY
    global banknifty_future
    start_time = int(9) * 60 + int(15)  # specify in int (hr) and int (min) formate
    end_time = int(17) * 60 + int(10)  # do not place fresh order
    stop_time = int(17) * 60 + int(15)  # square off all open positions
    last_time = start_time
    schedule_interval = 900  # run at every 15 min
    run_count = 0
    while True:
        if (datetime.datetime.now().hour * 60 + datetime.datetime.now().minute) >= end_time:
            if (datetime.datetime.now().hour * 60 + datetime.datetime.now().minute) >= stop_time:
                log_current_holdings()
                log("Trading day closed, time is above stop_time")
                break

        elif (
                datetime.datetime.now().hour * 60 + datetime.datetime.now().minute) >= start_time and datetime.datetime.now().minute % 15 == 0:
            if time.time() >= last_time:
                last_time = time.time() + schedule_interval
                print(tracemalloc.get_traced_memory())
                log("\n\n {} Run Count : Time - {} ".format(run_count, datetime.datetime.now()))
                if run_count >= 0:
                    try:
                        """nifty = False
                        x = get_data('^NSEBANK')
                        dravs(x)"""
                        NIFTY = True
                        log_current_holdings()
                        orders = get_data_new('^NSEBANK')
                        psar_trading_strategy(orders, banknifty_future)
                        print(orders.iloc[8, 1])
                        print("done")
                        print("running ", datetime.datetime.now(), POSITIONS)
                        time.sleep(schedule_interval)
                    except Exception as e:
                        print("Run error", e)
                run_count = run_count + 1
                print(tracemalloc.get_traced_memory())
        else:
            print('     Waiting...', datetime.datetime.now())
            if datetime.datetime.now().minute % 15 == 0:
                time.sleep(900)
            else:
                #print('none')
                time.sleep((15 - datetime.datetime.now().minute % 15) * 60 - datetime.datetime.now().second)




def check_and_update_daily_active_position():
    daily_positions = sas.get_daywise_positions()['data']
    return daily_positions
def log_current_holdings():
    holdings = iter(sas.get_holding_positions()['data']['holdings'])
    # print(type(holdins))
    pnl_list = []
    message = ''
    for i in holdings:
        #time.sleep(1)
        actualValue = i['previous_close'] * i['quantity']
        avgValue = i['actual_buy_avg'] * i['quantity']
        profit_or_loss = actualValue - avgValue
        pnl_list.append(profit_or_loss)
        message =message + "{} : {} |  {} : {} | {} : {} | {} : {} | {} : {} | {} : {} ".format("SYMBOL", i['instrument_details'][
            'trading_symbol'], "BUY VALUE", i['buy_avg'], "QUANTITY", i['quantity'], "ACTUAL VALUE", actualValue,
                                                                                 "AVERAGE VALUE", avgValue,
                                                                                 "profit or loss ", profit_or_loss)+"\n"
    message = message + " {} : {} ".format("TOTAL HOLDINGS PNL", sum(pnl_list))
    log(message)

#d=check_and_update_daily_active_position()
# run()
#NIFTY_FUTURE = sas.get_instrument_for_fno(symbol='NIFTY', expiry_date=expiry_date, is_fut=True, strike=None,
#                                          is_call=False)

"""
log(" trade book  \n"+str(sas.get_trade_book()['data']))
log("daily active positions   "+str(check_and_update_daily_active_position()))
print(sas.get_profile())

irfc = sas.get_instrument_by_symbol('NSE', 'IRFC')

run()






#print("holding positions "+str(sas.get_holding_positions()['data']['holdings']))
#buy_signal(irfc, 1)
#sell_signal(nifty_future,25)
NIFTY = True
x = get_data('^NSEI')
supertrend_trading_strategy(x)
netPositions = sas.get_netwise_positions()

print("net wise positions "+str(sas.get_netwise_positions()))


log_current_holdings()



print("done")"""

#
tracemalloc.start()
orders = get_data_new('^NSEBANK')
psar_trading_strategy(orders, banknifty_future)
run()

tracemalloc.stop()
print("y")
