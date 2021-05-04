import os
import asyncio
import sys
sys.path.append('../')
sys.path.append('../../')
from multiprocessing import Pool
from threading import Thread
import time

from dquant.markets._binance_spot_rest import Binance
from dquant.markets._bitfinex_spot_rest import TradingV1
from dquant.markets._huobi_spot_rest import HuobiRest
from dquant.markets._okex_spot_rest import OkexSpotRest
from dquant.constants import Constants


def task_bi(meta_code):
    #os.environ[Constants.DQUANT_ENV] = "dev"
    bi = Binance(meta_code)
    bi.start()
    bi.get_trades()


def task_bfx(meta_code):
    #os.environ[Constants.DQUANT_ENV] = "dev"
    trading = TradingV1(meta_code)
    #trading = TradingV1('eth_usd')
    trading.get_trades()

'''
def task_huobi(meta_code):
    #os.environ[Constants.DQUANT_ENV] = "dev"
    loop = asyncio.new_event_loop()
    hb = HuobiRest(meta_code, loop)
    hb.start()
    #hb.setDaemon(True)
    print(111)
    hb.get_trades()
    print(222)
'''

def task_ok(meta_code):
    #os.environ[Constants.DQUANT_ENV] = "dev"
    ok = OkexSpotRest(meta_code)
    ok.get_trades()


class task_huobi(Thread):

    def __init__(self, meta_code):
        super().__init__()
        self.loop = asyncio.new_event_loop()
        self.meta_code = meta_code
        self.hb = HuobiRest(self.meta_code, self.loop)
        self.hb.setDaemon(True)

    def run(self):
        self.hb.start()
        self.hb.get_trades()


def put_to_db_loop(tasks):

    for one in tasks:
        func = one['func']
        metas = one['metas']
        hb = []
        for meta_code in metas:
            print('func: ',func, 'meta_code: ', meta_code)

            hb.append(func(meta_code))
            time.sleep(1)
            #t = Thread(target=func, args=(meta_code, loop))
            #t.start()

        for h in hb:
            h.start()

        for h in hb:
            h.join()

def put_to_db(tasks):

    for one in tasks:
        func = one['func']
        metas = one['metas']
        hb = []
        for meta_code in metas:
            print('func: ',func, 'meta_code: ', meta_code)

            hb.append(func(meta_code))
            time.sleep(1)

        for h in hb:
            h.start()

        #for h in hb:
        #    h.join()


if __name__ == '__main__':

    #{'BNBBTC', 'BTCUSDT', 'BNBUSDT', 'LTCETH', 'LTCBNB', 'BCCUSDT', 'ETHUSDT', 'BCCBNB', 'BCCBTC', 'VENBNB', 'BNBETH', 'VENETH', 'ETHBTC', 'BCCETH', 'LTCBTC', 'LTCUSDT'}

    symbol_list = ['bnb_btc', 'btc_usdt', 'bnb_usdt', 'ltc_eth', 'ltc_bnb', 'bcc_usdt', 'eth_usdt', 'bcc_bnb',
                   'bcc_btc', 'ven_bnb', 'bnb_eth', 'ven_eth', 'eth_btc', 'bcc_eth', 'ltc_btc', 'ltc_usdt']

    symbol_list_hb = ['btc_usdt', 'bch_usdt', 'eth_usdt', 'bch_btc', 'ven_eth', 'eth_btc', 'ltc_btc', 'ltc_usdt']

    symbol_list_bfx = ['btc_usd', 'ltc_eth', 'bcc_usd', 'eth_usd', 'bcc_btc', 'ven_eth', 'eth_btc', 'bcc_eth', 'ltc_btc', 'ltc_usd']
    os.environ[Constants.DQUANT_ENV] = "dev"
    tasks_hb =[
        #{'func': task_bi, 'metas': symbol_list},
        #{'func': task_bfx, 'metas': symbol_list},
        {'func': task_huobi, 'metas': symbol_list_hb},
        #{'func': task_ok, 'metas': symbol_list}
    ]
    #put_to_db_loop(tasks_hb)


    tasks =[
        #{'func': task_bi, 'metas': symbol_list},
        {'func': task_bfx, 'metas': symbol_list_bfx},
        #{'func': task_huobi, 'metas': symbol_list_hb},
        #{'func': task_ok, 'metas': symbol_list}
    ]
    put_to_db(tasks)
