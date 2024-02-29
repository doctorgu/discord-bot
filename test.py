import asyncio
from binance import Client
from enum import IntEnum, unique
from dataclasses import dataclass

@dataclass
class Template:
    order_count: int
    add_last_one: True
    balance_to_keep: int
    percent_buy: float
    percent_sell: float
    quarter_buy: float
    quarter_sell: float
    qty_first_buy: int
    qty_first_sell: int
    qty_mult_buy: float
    qty_mult_sell: float

@unique
class KL(IntEnum):
    _0_OPEN_TIME = 0
    _1_OPEN = 1
    _2_HIGH = 2
    _3_LOW = 3
    _4_CLOSE = 4
    _5_VOLUME = 5
    _6_CLOSE_TIME = 6
    _7_QUOTE_ASSET_VOLUME = 7
    _8_NUMBER_OF_TRADES = 8
    _9_TAKER_BUY_BASE_ASSET_VOLUME = 9
    _10_TAKER_BUY_QUOTE_ASSET_VOLUME = 10

def get_decimal_places(number):
    """
    print(get_decimal_places(123.456))  # Outputs: 3
    print(get_decimal_places(123))      # Outputs: 0
    """

    count = 0
    remainder = number - int(number)
    while remainder != 0 and count < 15:  # Limit to 15 to avoid infinite loop due to floating point precision
        number *= 10
        remainder = number - int(number)
        count += 1
    return count

def get_exchange_info(client, quoteAsset):
    exchange_info = client.get_exchange_info()

    infos = {}

    for symbol_ in exchange_info['symbols']:
        if symbol_['quoteAsset'] != quoteAsset\
        or not symbol_['isMarginTradingAllowed']\
        or symbol_['status'] != 'TRADING':
            continue

        symbol = symbol_['symbol']
        baseAsset = symbol_['baseAsset']
        quoteAsset = symbol_['quoteAsset']

        tickSize, minPrice, maxPrice = 0, 0, 0
        stepSize, minQty, maxQty = 0, 0, 0
        for filter in symbol_['filters']:
            if filter['filterType'] == 'PRICE_FILTER':
                tickSize = float(filter['tickSize'])
                minPrice = float(filter['minPrice'])
                maxPrice = float(filter['maxPrice'])
            elif filter['filterType'] == 'LOT_SIZE':
                stepSize = float(filter['stepSize'])
                minQty = float(filter['minQty'])
                maxQty = float(filter['maxQty'])

            if tickSize != 0 and stepSize != 0:
                break

        price_decimals = get_decimal_places(tickSize)
        qty_decimals = get_decimal_places(stepSize)

        infos[symbol] = {
            'baseAsset': baseAsset,
            'quoteAsset': quoteAsset,

            'price_decimals': price_decimals,
            'qty_decimals': qty_decimals,

            'minPrice': minPrice,
            'maxPrice': maxPrice,

            'minQty': minQty,
            'maxQty': maxQty,
        }

    return infos

async def get_templates_busy(client, exchange_info, symbols_except,
                              ratio=0.003, top_n=30, min_trade_volume=100_000, max_total_balance=100_000):
    def get_simulated(klines, ratio, bought_init):
        kline_0 = klines[0]

        cur = float(kline_0[KL._1_OPEN])
        count = 0
        bought = bought_init
        for kline in klines:
            high = float(kline[KL._2_HIGH])
            low = float(kline[KL._3_LOW])

            if bought:
                target = round(cur + (cur * ratio), 8)
                if high > target:
                    cur = target
                    count += 1
                    bought = not bought
            else:
                target = round(cur - (cur * ratio), 8)
                if low < target:
                    cur = target
                    count += 1
                    bought = not bought
        return count
    
    symbols = [symbol for symbol in exchange_info if symbol not in symbols_except]

    counts = { symbol: { 'count': 0, 'trade_volume': 0 } for symbol in symbols }
    for symbol in symbols:
        klines = client.get_historical_klines(symbol, Client.KLINE_INTERVAL_1MINUTE, "1 hours ago UTC")

        trade_volume = sum([float(kline[KL._5_VOLUME]) * float(kline[KL._1_OPEN]) for kline in klines])
        if trade_volume < min_trade_volume:
            continue

        count1 = get_simulated(klines, ratio, bought_init=True)
        count2 = get_simulated(klines, ratio, bought_init=False)
        counts[symbol] = { 'count': max(count1, count2), 'trade_volume': round(trade_volume, 0) }

    counts_rank = dict(sorted(counts.items(), key=lambda x: x[1]['count'], reverse=True)[:top_n])

    templates = {}
    total_balance = 0
    for symbol in counts_rank:
        qty_decimals = exchange_info[symbol]['qty_decimals']

        trade_volume = counts_rank[symbol]['trade_volume']
        balance_to_keep = round(trade_volume / 600, 0)
        total_balance += balance_to_keep
        if total_balance > max_total_balance:
            break

        qty_first = round(balance_to_keep / 100, qty_decimals)

        template = Template(
            order_count=6,
            add_last_one=True,
            balance_to_keep=balance_to_keep,
            percent_buy=0.3,
            percent_sell=0.3,
            quarter_buy=0,
            quarter_sell=0,
            qty_first_buy=qty_first,
            qty_first_sell=qty_first,
            qty_mult_buy=1.23,
            qty_mult_sell=1.23,
        )
        templates[symbol] = template

    return templates
    # for symbol in templates:
    #     symbol_ = counts_rank[symbol]
    #     template = templates[symbol]
    #     print(f'{symbol},{symbol_["count"]},{symbol_["trade_volume"]},{template}')

client = Client()
exchange_info = get_exchange_info(client, 'USDT')
asyncio.run(get_templates_busy(client, exchange_info, [], 0.003, 40))
client.close_connection()

