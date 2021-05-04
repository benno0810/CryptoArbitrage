import os
import time

from dquant.constants import Constants
from dquant.common.mongo_conn import MongoConnOrder


'''
bch_btc, bch_eth, btc_usdt, eos_btc, eos_eth, eth_btc, eth_usdt
'''

ips = ['172.31.18.172', '172.31.22.135']
mkts = ['HuoBiPro', 'OKEX', 'Bitfinex']
apis = ['buy', 'cancel', 'depth']
symbols = ['bch_btc', 'bch_eth', 'btc_usdt', 'eos_btc', 'eos_eth', 'eth_btc', 'eth_usdt', 'bchbtc', 'bcheth', 'btcusdt', 'eosbtc', 'eoseth', 'ethbtc', 'ethusdt',
           'tBCHBTC', 'tBCHETH', 'tBTCUSDT', 'tEOSBTC', 'tEOSETH', 'tETHBTC', 'tETHUSDT']


def get_profit_loss_bfx():

    db = MongoConnOrder().client.account

    bfx = db.orders_bitfinex.find({'order_time': {'$gt': 1520904284876}, 'trade_pair': 'ETHUSD'})

    print('bfx count: {}'.format(bfx.count()))

    total_amount = 0
    total_price = 0

    for one in bfx:
        print(time.ctime(one['order_time']/1000.0), one['amount_filled'], one['price'])
        total_amount += one['amount_filled']
        total_price += one['amount_filled']*one['price']

    print('bfx amount: {}, bfx avg_price: {}'.format(total_amount, total_price/total_amount))


def get_profit_loss_okex():

    db = MongoConnOrder().client.account

    ok = db.orders_okex_spot.find({'order_time': {'$gt': 1520904284876}, 'trade_pair': 'eth_usdt'})

    print('ok count: {}'.format(ok.count()))

    total_amount = 0
    total_price = 0
    for one in ok:
        print(time.ctime(one['order_time']/1000.0), one['amount_filled'], one['price'])
        total_amount += one['amount_filled']
        total_price += one['amount_filled']*one['price']

    print('okex amount: {}, okex avg_price: {}'.format(total_amount, total_price/total_amount))


def get_profit_loss_huobi():

    db = MongoConnOrder().client.account

    hb = db.orders_huobi.find({'order_time': {'$gt': 1520904284876}, 'trade_pair': 'ethusdt'})

    print('hb count: {}'.format(hb.count()))

    total_amount = 0
    total_price = 0
    for one in hb:
        print(time.ctime(one['order_time']/1000.0), one['amount_filled'], one['price'])
        total_amount += one['amount_filled']
        total_price += one['amount_filled']*one['price']

    print('huobi amount: {}, huobi avg_price: {}'.format(total_amount, total_price/total_amount))


if __name__ == '__main__':
    os.environ[Constants.DQUANT_ENV] = "pro"
    get_profit_loss_bfx()
    #get_profit_loss_okex()
    #get_profit_loss_huobi()