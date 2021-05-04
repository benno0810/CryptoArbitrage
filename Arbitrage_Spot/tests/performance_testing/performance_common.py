import sys
sys.path.append('../')
sys.path.append('../../')
import time
import os
import threading

#from dquant.common.mongo_conn import MongoConn as MongoConnOrder
from dquant.common.mongo_conn import MongoConnOrder
from dquant.constants import Constants
from dquant.util import get_ip
from dquant.common.depth_log import init_roll_log


os.environ[Constants.DQUANT_ENV] = "dev"

logger = init_roll_log('performance_get_account.log')


'''
1. 新开一台机器，对每个交易所的三个币种btc/usd，eth/btc，eth/usd进行下单撤单操作
2. 间隔0.1/0.5/1/2s进行测试，确认会不会在这个时间出现被ban的情况，以及latency。
3. 开两台机器，用同一个key进行测试，查看是否可以通过多开机器的方式使得不会被ban
4. 币安优先测试，之后是huobi和bfx，最后ok

rest: binance huobi
ws: bfx, okex
'''


class Performance(threading.Thread):

    def __init__(self, mkt):
        super().__init__()
        self.sleep = 20
        self.mkt = mkt
        self.col = MongoConnOrder().client.latency.api_latency
        self.ip = get_ip()

    def buy(self):
        pass

    def test_buy_cancel(self):
        s_time_buy = time.time()
        res_b = self.buy()
        e_time_buy = time.time()

        buy_used = e_time_buy - s_time_buy
        self.col.insert({'timestamp': int(time.time()*1000), 'lantency': buy_used*1000, 'api': 'buy',
                         'market': self.mkt.name, 'symbol': self.mkt.symbol, 'ip': self.ip})

        logger.debug('{}:{}:{:.8f}:{}'.format(self.mkt.name, 'buy', buy_used, int(e_time_buy*1000)))

        print('mkt: {}, buy res: {}'.format(self.mkt, res_b))
        if res_b and res_b.get('order_id', 0) :
            s_time_del = time.time()
            self.mkt.deleteOrder(res_b['order_id'])
            e_time_del = time.time()

            del_used = e_time_del - s_time_del
            self.col.insert({'timestamp': int(time.time() * 1000), 'lantency': del_used * 1000, 'api': 'cancel',
                             'market': self.mkt.name, 'symbol': self.mkt.symbol, 'ip': self.ip})
            logger.debug('{}:{}:{:.8f}:{}'.format(self.mkt.name, 'cancel', buy_used, int(e_time_buy * 1000)))

    def run(self):
        while True:
            try:
                self.test_buy_cancel()
                time.sleep(self.sleep)
            except Exception as e:
                print(e)


class PerformanceGetAccount(threading.Thread):

    def __init__(self, mkt):
        super().__init__()
        self.sleep = 20
        self.mkt = mkt
        self.ip = get_ip()

    def get_account(self):
        s_time = time.time()
        res = self.mkt.getAccount()
        e_time = time.time()
        time_used = (e_time - s_time)*1000
        logger.debug('{}:{}:{:.8f}:{}'.format(self.mkt.name, sys._getframe().f_code.co_name, time_used, int(e_time*1000)))
        return res

    def run(self):
        while True:
            try:
                self.get_account()
                time.sleep(self.sleep)
            except Exception as e:
                print(e)