import threading
import time
import logging
from dquant.common.mongo_conn import MongoConnOrder
from dquant.config import cfg
from dquant.constants import Constants
logger = logging.getLogger(__name__)


class OrderMonitor(threading.Thread):
    def __init__(self, queue):
        super(OrderMonitor, self).__init__()
        self.monitor = cfg.get_bool_config(Constants.MONITOR)
        self.q = queue
        self.client = MongoConnOrder().client
        self.db = self.client.account
        self.platform_id_table = {'bitfinex':self.db.orders_bitfinex, 'binance':self.db.orders_binance, 'huobi':self.db.orders_huobi, 'okex_spot':self.db.orders_okex_spot, 'okex_future':self.db.orders_okex_future}
        self.last_order_id = None

    def run(self):
        if not self.monitor:
            logger.info('Monitor config: False')
            return
        while True:
            try:
                message = self.q.get()
                platform_id = message['platform_id']
                if self.last_order_id == message['order_id']:
                    continue
                else:
                    self.last_order_id = message['order_id']
                    self.platform_id_table[platform_id].update({'order_id': message['order_id']}, {'$setOnInsert': message}, upsert=True)
                    # self.platform_id_table[platform_id].insert_one(message)
                    # logging.info('%s: %s' % (platform_id, message))
                    time.sleep(0.001)
            except Exception as ex:
                logger.error("{}: {}".format(self.__class__, str(ex)),
                             exc_info=True)


class CancelledOrderMonitor(OrderMonitor):
    """继承OrderMonitor，但是只存储cancel的订单"""

    def __init__(self, queue):
        super(CancelledOrderMonitor, self).__init__(queue)
        self.platform_id_table = {
            "bitfinex": self.db.cancelled_orders_bitfinex,
            "binance": self.db.cancelled_orders_binance,
            "huobi": self.db.cancelled_orders_huobi,
            "okex_spot": self.db.cancelled_orders_okex_spot,
            "okex_future": self.db.cancelled_orders_okex_future
        }



class OrderResultMonitor(OrderMonitor):
    """继承OrderMonitor，会记录每笔buy()/sell()操作的结果"""

    def __init__(self, queue):
        super(OrderResultMonitor, self).__init__(queue)
        self.platform_id_table = {
            "bitfinex": self.db.orders_result_bitfinex,
            "binance": self.db.orders_result_binance,
            "huobi": self.db.orders_result_huobi,
            "okex_spot": self.db.orders_result_okex_spot
        }

    def run(self):
        if not self.monitor:
            logger.info('Monitor config: False')
            return
        while True:
            try:
                message = self.q.get()
                platform_id = message['platform_id']
                self.platform_id_table[platform_id].insert_one(message)
                time.sleep(0.001)
            except Exception as ex:
                logger.error("{}: {}".format(self.__class__, str(ex)),
                             exc_info=True)


class MakerMonitor(threading.Thread):
    def __init__(self, queue):
        super(MakerMonitor, self).__init__()
        self.monitor = cfg.get_bool_config(Constants.MONITOR)
        self.q = queue
        self.client = MongoConnOrder().client
        self.db = self.client.account
        self.platform_id_table = {'bitfinex':self.db.maker_bitfinex, 'binance':self.db.maker_binance, 'huobi':self.db.maker_huobi, 'okex_spot':self.db.maker_okex_spot, 'okex_future':self.db.orders_okex_future}
        self.last_order_id = None

    def run(self):
        if not self.monitor:
            logger.info('Monitor config: False')
            return
        while True:
            try:
                message = self.q.get()
                # print('message: ', message)
                platform_id = message['platform_id']
                if self.last_order_id == message['order_id']:
                    continue
                else:
                    self.last_order_id = message['order_id']
                    self.platform_id_table[platform_id].update({'order_id': message['order_id']}, {'$setOnInsert': message}, upsert=True)
                    # self.platform_id_table[platform_id].insert_one(message)
                    # logging.info('%s: %s' % (platform_id, message))
                    time.sleep(0.001)
            except Exception as ex:
                logger.error("MakerMonitor: %s" % ex)
