import websocket, json, requests, sys, hashlib, hmac
import dateutil.parser, time
from config import BX_API_KEY, BX_API_SECRET, BX_PAIR, BX_QTY, CB_PAIR, BX_SYMBOL, MIN_DISTANCE

minutes_processed = {}
minute_candlesticks = []
current_tick = None
previous_tick = None
profit_price = None
loss_price = None

BASE_URL = "https://api.bittrex.com/api/v1.1"
ACCOUNT_URL = "{}/account/getbalances".format(BASE_URL)
SYMBOL_URL = "{}/account/getbalance".format(BASE_URL)
SELLLIMIT_URL = "{}/market/selllimit".format(BASE_URL)
BUYLIMIT_URL = "{}/market/buylimit".format(BASE_URL)
API_TIMESTAMP = str(round(time.time() * 1000))


def on_open(ws):
    print("opened connection")

    subscribe_message = {
        "type": "subscribe",
        "channels": [
            {
                "name":  "ticker",
                "product_ids": [
                    CB_PAIR
                ]
            }
        ]
    }

    ws.send(json.dumps(subscribe_message))


def get_balance(BX_SYMBOL):
    MESSAGE = '?apikey=' + BX_API_KEY + '&nonce=' + API_TIMESTAMP + '&currency=' + BX_SYMBOL
    LIST = [SYMBOL_URL, MESSAGE]
    PRESIGN = "".join(LIST)
    SIGNATURE = hmac.new(BX_API_SECRET.encode(), msg=PRESIGN.encode(), digestmod=hashlib.sha512).hexdigest()
    CT= "application/json"
    
    HEADERS = {'Content-Type': CT, 'apisign': SIGNATURE}
    r = requests.post(PRESIGN, headers=HEADERS)
    response = json.loads(r.content)
    filter_response = response['result']['Balance']

    return(filter_response)


def on_message(ws, message):
    global current_tick, previous_tick, in_position, loss_price, profit_price

    previous_tick = current_tick
    current_tick = json.loads(message)
    in_position = "{:.4f}".format(float(get_balance(BX_SYMBOL)))

    #print(current_tick)
    print("=== Received Tick ===")
    print("{} @ {}".format(current_tick['time'], current_tick['price']))
    tick_datetime_object = dateutil.parser.parse(current_tick['time'])
    tick_dt = tick_datetime_object.strftime("%m/%d/%Y %H:%M")
    
    print(tick_datetime_object.minute)
    print(tick_dt)

    if not tick_dt in minutes_processed:
        print("starting new candlestick")
        minutes_processed[tick_dt] = True
        print(minutes_processed)

        if len(minute_candlesticks) > 0:
            minute_candlesticks[-1]['close'] = previous_tick['price']
        
        minute_candlesticks.append({
            "minute": tick_dt,
            "open": current_tick['price'],
            "high": current_tick['price'],
            "low": current_tick['price']
        })

    if len(minute_candlesticks) > 0:
        current_candlestick = minute_candlesticks[-1]
        if current_tick['price'] > current_candlestick['high']:
            current_candlestick['high'] = current_tick['price']
        if current_tick['price'] < current_candlestick['low']:
            current_candlestick['low'] = current_tick['price']

    print("== Candlesticks ==")
    for candlestick in minute_candlesticks[-5:]:
        print(candlestick)

    if len(minute_candlesticks) > 4:
        print("== there are more than 4 candlesticks, checking for pattern ==")
        last_candle = minute_candlesticks[-2]
        previous_candle = minute_candlesticks[-3]
        first_candle = minute_candlesticks[-4]
        zero_candle = minute_candlesticks[-5]

        if in_position == "0.0000":
            print("== let's compare the last 3 closes ==")
            if last_candle['close'] > previous_candle['close'] and previous_candle['close'] > first_candle['close'] and first_candle['close'] > zero_candle['close']:
                print("=== Three green candlesticks in a row, let's make a trade! ===")
                distance = int(float(last_candle['close'])) - int(float(zero_candle['close']))
                min_distance_int = int(MIN_DISTANCE)
                print("Distance is {}".format(distance))
                if distance > min_distance_int:
                    profit_price = int(float(last_candle['close'])) + (distance * 2)
                    print("I will take profit at {}".format(profit_price))
                    loss_price = zero_candle['close']
                    print("I will sell for a loss at {}".format(loss_price))
                    purchase_price = int(float(current_tick['price'])) + int(10)
                    purchase_price_str = str(purchase_price)
                    place_buylimit_order(purchase_price_str)
                    time.sleep(10)
                else:
                    print("Distance must be more than {}".format(MIN_DISTANCE))
            else:
                print("No Soldiers")
        else:
            print("== Attempting to Sell ==")
            print("I will take profit at {}".format(profit_price))
            print("I will sell for a loss at {}".format(loss_price))
            if current_tick['price'] > str(profit_price):
                print("== Selling for Profit ==")
                sell_profit_price = int(profit_price) - 10
                sell_profit_price_str = str(sell_profit_price)
                place_selllimit_profit_order(sell_profit_price_str)
                time.sleep(10)
            elif current_tick['price'] < str(loss_price):
                print("== Selling at Loss ==")
                sell_loss_price = int(float(current_tick['price'])) - int(10)
                sell_loss_price_str = str(sell_loss_price)
                place_selllimit_loss_order(sell_loss_price_str)
                time.sleep(10)
            else:
                print(current_tick['price'])


def place_selllimit_profit_order(sell_profit_price_str):
    MESSAGE = '?apikey=' + BX_API_KEY + '&nonce=' + API_TIMESTAMP + '&market=' + BX_PAIR + '&quantity=' + BX_QTY + '&rate=' + sell_profit_price_str
    LIST = [SELLLIMIT_URL, MESSAGE]
    PRESIGN = "".join(LIST)
    SIGNATURE = hmac.new(BX_API_SECRET.encode(), msg=PRESIGN.encode(), digestmod=hashlib.sha512).hexdigest()
    CT= "application/json"
    
    HEADERS = {'Content-Type': CT, 'apisign': SIGNATURE}
    r = requests.post(PRESIGN, headers=HEADERS)
    response = json.loads(r.content)

    print(response)


def place_selllimit_loss_order(sell_loss_price_str):
    MESSAGE = '?apikey=' + BX_API_KEY + '&nonce=' + API_TIMESTAMP + '&market=' + BX_PAIR + '&quantity=' + BX_QTY + '&rate=' + sell_loss_price_str
    LIST = [SELLLIMIT_URL, MESSAGE]
    PRESIGN = "".join(LIST)
    SIGNATURE = hmac.new(BX_API_SECRET.encode(), msg=PRESIGN.encode(), digestmod=hashlib.sha512).hexdigest()
    CT= "application/json"
    
    HEADERS = {'Content-Type': CT, 'apisign': SIGNATURE}
    r = requests.post(PRESIGN, headers=HEADERS)
    response = json.loads(r.content)

    print(response)


def place_buylimit_order(purchase_price_str):
    MESSAGE = '?apikey=' + BX_API_KEY + '&nonce=' + API_TIMESTAMP + '&market=' + BX_PAIR + '&quantity=' + BX_QTY + '&rate=' + purchase_price_str
    LIST = [BUYLIMIT_URL, MESSAGE]
    PRESIGN = "".join(LIST)
    SIGNATURE = hmac.new(BX_API_SECRET.encode(), msg=PRESIGN.encode(), digestmod=hashlib.sha512).hexdigest()
    CT= "application/json"
    
    HEADERS = {'Content-Type': CT, 'apisign': SIGNATURE}
    r = requests.post(PRESIGN, headers=HEADERS)
    response = json.loads(r.content)

    print(response)


def on_close(ws):
    print("closed connection")


socket = "wss://ws-feed.pro.coinbase.com"


ws = websocket.WebSocketApp(socket, on_open=on_open, on_message=on_message, on_close=on_close)
ws.run_forever()