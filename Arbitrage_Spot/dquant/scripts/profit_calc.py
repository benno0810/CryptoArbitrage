import os
import time
import json
from pprint import pprint

from os.path import exists

from dquant.scripts.txtparse import get_huobi_price, JsonParser

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
os.sys.path.append(rootPath)

from dquant.common.mongo_conn import MongoConn


def fee_calc(d, output):
    if 'fee' not in d:
        print("document %s has no fee record" % d)
    else:
        strategy_id = d['strategy_id']
        f = d['fee']
        f_amount = float(f.split("_")[0])
        f_unit = f.split("_")[1]
        if f_unit.upper() in ['USD', 'USDT']:
            output[strategy_id]['fee']['usdt'] += f_amount
        elif f_unit.upper() in ['ETH']:
            output[strategy_id]['fee']['eth'] += f_amount
        elif f_unit.upper() in ['BTC']:
            output[strategy_id]['fee']['btc'] += f_amount
        elif f_unit.upper() in ['EOS']:
            output[strategy_id]['fee']['eos'] += f_amount
        elif f_unit.upper() in ['BCC', 'BCH']:
            output[strategy_id]['fee']['bch'] += f_amount
        else:
            print("Unknown fee unit: %s" % f_unit)


def vol_calc(d, output):
    strategy_id = d['strategy_id']
    if d['trade_pair'].upper() in ['ETHBTC', 'ETH_BTC']:
        output[strategy_id]['volume']['eth'] += d['amount_filled']
    elif d['trade_pair'].upper() in ['ETHUSDT', 'ETHUSD', 'ETH_USDT', 'ETH_USD']:
        output[strategy_id]['volume']['eth'] += d['amount_filled']
    elif d['trade_pair'].upper() in ['EOSETH', 'EOS_ETH', 'EOSBTC', 'EOS_BTC']:
        output[strategy_id]['volume']['eos'] += d['amount_filled']
    elif d['trade_pair'].upper() in ['BCCETH', 'BCC_ETH', 'BCHETH', 'BCH_ETH', 'BCCBTC', 'BCC_BTC', 'BCHBTC',
                                     'BCH_BTC']:
        output[strategy_id]['volume']['bch'] += d['amount_filled']
    elif d['trade_pair'].upper() in ['BTCUSDT', 'BTCUSD', 'BTC_USDT', 'BTC_USD']:
        output[strategy_id]['volume']['btc'] += d['amount_filled']
    else:
        print('还有{}这个交易对没告诉我'.format(d['trade_pair']))


def eth_calc_profit(bs, sell=True, output=None):
    if sell:
        for s in bs:
            market = s['platform_id']
            strategy_id = s['strategy_id']
            if strategy_id not in output:
                output[strategy_id] = {'profit' : {'btc': 0.0, 'eth': 0.0, 'eos': 0.0, 'bch': 0.0, 'usdt':0.0},
                                     'volume': {'btc': 0.0, 'eth': 0.0, 'eos': 0.0, 'bch': 0.0, 'usdt':0.0},
                                     'fee': {'btc': 0.0, 'eth': 0.0, 'eos': 0.0, 'bch': 0.0, 'usdt':0.0},
                                     'net_profit': {'btc': 0.0, 'eth': 0.0, 'eos': 0.0, 'bch': 0.0, 'usdt':0.0}}

            if s['trade_pair'].upper() in ['ETHBTC', 'ETH_BTC']:
                output[strategy_id]['profit']['btc'] += s['amount_filled'] * s['price']
                output[strategy_id]['profit']['eth'] -= s['amount_filled']
            elif s['trade_pair'].upper() in ['ETHUSDT', 'ETHUSD', 'ETH_USDT', 'ETH_USD']:
                output[strategy_id]['profit']['usdt'] += s['amount_filled'] * s['price']
                output[strategy_id]['profit']['eth'] -= s['amount_filled']
            elif s['trade_pair'].upper() in ['EOSETH', 'EOS_ETH']:
                output[strategy_id]['profit']['eth'] += s['amount_filled'] * s['price']
                output[strategy_id]['profit']['eos'] -= s['amount_filled']
            elif s['trade_pair'].upper() in ['EOSBTC', 'EOS_BTC']:
                output[strategy_id]['profit']['btc'] += s['amount_filled'] * s['price']
                output[strategy_id]['profit']['eos'] -= s['amount_filled']
            elif s['trade_pair'].upper() in ['BCCETH', 'BCC_ETH', 'BCHETH', 'BCH_ETH']:
                output[strategy_id]['profit']['eth'] += s['amount_filled'] * s['price']
                output[strategy_id]['profit']['bch'] -= s['amount_filled']
            elif s['trade_pair'].upper() in ['BCCBTC', 'BCC_BTC', 'BCHBTC', 'BCH_BTC']:
                output[strategy_id]['profit']['btc'] += s['amount_filled'] * s['price']
                output[strategy_id]['profit']['bch'] -= s['amount_filled']
            elif s['trade_pair'].upper() in ['BTCUSDT', 'BTCUSD', 'BTC_USDT', 'BTC_USD']:
                output[strategy_id]['profit']['usdt'] += s['amount_filled'] * s['price']
                output[strategy_id]['profit']['btc'] -= s['amount_filled']
            else:
                print('还有{}这个交易对没告诉我'.format(s['trade_pair']))
            fee_calc(s, output=output)
    else:
        for b in bs:
            strategy_id = b['strategy_id']
            if strategy_id not in output:
                output[strategy_id] = {'profit' : {'btc': 0.0, 'eth': 0.0, 'eos': 0.0, 'bch': 0.0, 'usdt':0.0},
                                     'volume': {'btc': 0.0, 'eth': 0.0, 'eos': 0.0, 'bch': 0.0, 'usdt':0.0},
                                     'fee': {'btc': 0.0, 'eth': 0.0, 'eos': 0.0, 'bch': 0.0, 'usdt':0.0},
                                     'net_profit': {'btc': 0.0, 'eth': 0.0, 'eos': 0.0, 'bch': 0.0, 'usdt':0.0}}

            if b['trade_pair'].upper() in ['ETHBTC', 'ETH_BTC']:
                output[strategy_id]['profit']['btc'] -= b['amount_filled'] * b['price']
                output[strategy_id]['profit']['eth'] += b['amount_filled']
            elif b['trade_pair'].upper() in ['ETHUSDT', 'ETHUSD', 'ETH_USDT', 'ETH_USD']:
                output[strategy_id]['profit']['usdt'] -= b['amount_filled'] * b['price']
                output[strategy_id]['profit']['eth'] += b['amount_filled']
            elif b['trade_pair'].upper() in ['EOSETH', 'EOS_ETH']:
                output[strategy_id]['profit']['eth'] -= b['amount_filled'] * b['price']
                output[strategy_id]['profit']['eos'] += b['amount_filled']
            elif b['trade_pair'].upper() in ['EOSBTC', 'EOS_BTC']:
                output[strategy_id]['profit']['btc'] -= b['amount_filled'] * b['price']
                output[strategy_id]['profit']['eos'] += b['amount_filled']
            elif b['trade_pair'].upper() in ['BCCETH', 'BCC_ETH', 'BCHETH', 'BCH_ETH']:
                output[strategy_id]['profit']['eth'] -= b['amount_filled'] * b['price']
                output[strategy_id]['profit']['bch'] += b['amount_filled']
            elif b['trade_pair'].upper() in ['BCCBTC', 'BCC_BTC', 'BCHBTC', 'BCH_BTC']:
                output[strategy_id]['profit']['btc'] -= b['amount_filled'] * b['price']
                output[strategy_id]['profit']['bch'] += b['amount_filled']
            elif b['trade_pair'].upper() in ['BTCUSDT', 'BTCUSD', 'BTC_USDT', 'BTC_USD']:
                output[strategy_id]['profit']['usdt'] -= b['amount_filled'] * b['price']
                output[strategy_id]['profit']['btc'] += b['amount_filled']
            else:
                print('还有{}这个交易对没告诉我'.format(b['trade_pair']))

            fee_calc(b, output=output)
            vol_calc(b, output=output)
    return output


def find_in_timestamp(curs, start_timestamp):
    ret = []
    for cur in curs:
        my_dict = []
        for document in cur:
            if start_timestamp <= document['order_time'] < start_timestamp + 24 * 3600 * 100:
                my_dict.append(document)
        ret.append(my_dict)
    return ret


def get_btc_eth_info(start_timestamp, db, output):
    end_timestamp = start_timestamp + 24 * 3600 * 1000

    sell_condition = {'order_time': {'$lte': end_timestamp, '$gte': start_timestamp}, 'side': {'$regex': 'sell'}}
    buy_condition = {'order_time': {'$lte': end_timestamp, '$gte': start_timestamp}, 'side': {'$regex': 'buy'}}
    print("finding in bi...")
    sell_bi = db.orders_binance.find(sell_condition)
    buy_bi = db.orders_binance.find(buy_condition)
    print("finding in bfx...")
    sell_bfx = db.orders_bitfinex.find(sell_condition)
    buy_bfx = db.orders_bitfinex.find(buy_condition)
    print("finding in hb...")
    sell_hb = db.orders_huobi.find(sell_condition)
    buy_hb = db.orders_huobi.find(buy_condition)
    print("finding in ok...")
    sell_ok = db.orders_okex_spot.find(sell_condition)
    buy_ok = db.orders_okex_spot.find(buy_condition)


    for s in [sell_bi, sell_bfx, sell_hb, sell_ok]:
        eth_calc_profit(s, output=output)
    for b in [buy_bi, buy_bfx, buy_hb, buy_ok]:
        eth_calc_profit(b, False, output=output)


    time_local = time.localtime(int(start_timestamp/1000))
    dt = time.strftime("%Y-%m-%d", time_local)
    put_in_json(dt, output)


def put_in_json(dt, output):
    for strategy_id, indicies in output.items():
        for coin in indicies['profit']:
            indicies['net_profit'][coin] = indicies['profit'][coin] - indicies['fee'][coin]
    pprint(dt)
    pprint(output)
    j = json.dumps({dt: output})
    with open("output.json", "a") as f:
        f.write(j)


def put_in_excel(dt, data, profit_data, row_c, sheet, fee_data):
    print(dt, data, row_c, fee_data)
    f_str = ">{};{};{}; profit:{}; fee:{}.\n".format(dt, data, row_c, profit_data, fee_data)
    with open("output.txt", "a") as f:
        f.write(f_str)
    sheet.write(row_c, 0, dt)
    for i in range(len(data)):
        sheet.write(row_c, i + 1, data[i])

    for j in range(len(data), len(data)+len(profit_data)):
        sheet.write(row_c, j + 1, profit_data[j-len(data)])


def start_calc(start_timestamp, end_timestamp, db):
    # global output
    row_c = 0
    # while start_timestamp <= end_timestamp - 24 * 3600 * 1000:
    output = {}
    get_btc_eth_info(start_timestamp, db, output)
    start_timestamp += 24 * 3600 * 1000
    row_c += 1

def get_start_timestamp(end_timestamp):
    '''
    :param end_timestamp: 结束时间戳
    :return: 返回当天0点的时间戳
    '''
    time_local = time.localtime(int(end_timestamp / 1000))
    dt = time.strftime("%Y-%m-%d", time_local)
    timeArray = time.strptime(dt, "%Y-%m-%d")
    timeStamp = int(time.mktime(timeArray))*1000
    return timeStamp


def check_txt_exist(file):
    if exists(file):
        os.remove(file)


if __name__ == '__main__':
    # start_timestamp = 1514736000000   # 1/1
    # end_timestamp = 1517587200000     #2/3
    # start_timestamp = 1520092800000     # 3/4
    # start_timestamp = 1519747200000   # 2/28
    # end_timestamp = 1520784000000       # 3/12
    # 移除已存在的txt文件
    file = "output.json"
    check_txt_exist(file)
    # 获取当前时间以及当日零点时间
    end_timestamp = int(time.time()*1000)
    start_timestamp = get_start_timestamp(end_timestamp)
    # 连接数据库查找并计算符合条件的记录
    mongo_address = '11111'
    mongo_port = 11111
    username = '11111'
    password = '11111'
    db = MongoConn(ip=mongo_address, port=mongo_port, username=username, password=password).client.account
    start_calc(start_timestamp, end_timestamp, db)

    print("-"*20)

    # price = {'ethbtc': 0.0777, 'ethusdt': 724, 'btcusdt': 9565,
    #          'eoseth':0.008260, 'eosbtc':0.00062677,
    #          'bcheth':1.53348, 'bchbtc':0.115750}

    metas = ['eth_btc', 'eth_usdt', 'btc_usdt', 'eos_eth', 'eos_btc', 'bch_btc']
    price = get_huobi_price(metas)
    price['bcheth'] = 1.51
    print(price)
    parser = JsonParser(file)
    parser.calc_with_price(price)