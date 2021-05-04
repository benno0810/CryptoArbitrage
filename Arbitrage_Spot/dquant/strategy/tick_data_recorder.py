import json
import logging
import queue
import threading

import time

import os

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
rootPath = os.path.split(rootPath)[0]
os.sys.path.append(rootPath)

from dquant.common.mongo_conn import MongoConnOrder

logger = logging.getLogger(__name__)


class Recorder(threading.Thread):
    Q = queue.Queue()
    TICK = 0
    TICK_LOCK = threading.Lock()

    def __init__(self, target_market, config_file):
        super().__init__()
        self.db = MongoConnOrder().client.account.maker_taker_data
        self.platform = target_market
        self.config = json.load(open(config_file, 'r'))
        self.strategy_id = self.config["strategy_id"]
        self.trade_pair = self.config["meta_code"]

    @staticmethod
    def _timestamp():
        return int(time.time()*1000)

    @classmethod
    def update_tick(cls, tick):
        with Recorder.TICK_LOCK:
            Recorder.TICK = int(tick)

    @staticmethod
    def _tick():
        with Recorder.TICK_LOCK:
            return Recorder.TICK

    @classmethod
    def record(cls, action, amount=0, price=0, order_id=0, taker_platform='', taker_task_order_id=0):
        '''
        :param action: maker_buy/maker_sell/maker_delete/maker_buy_filled/maker_sell_filled/taker_buy/taker_sell
        :param amount: amount
        :param price: price if maker else 0
        :param order_id: id
        :param taker_task_order_id: maker's order id if taker else 0
        :return:
        '''
        data = {"timestamp": Recorder._timestamp(),
                "tick": Recorder._tick(),
                "action": action,
                "amount": amount,
                "price": price,
                "order_id": order_id,
                "taker_platform": taker_platform,
                "taker_task_order_id": taker_task_order_id}
        Recorder.Q.put(data)

    def run(self):
        while True:
            try:
                data = Recorder.Q.get()
                data.update({"strategy_id": self.strategy_id,
                             "maker_platform": self.platform,
                             "trade_pair": self.trade_pair})
                self.db.insert_one(data)
            except Exception as ex:
                logger.error("Recorder error: %s" % ex)