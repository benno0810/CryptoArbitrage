import json
import os
import queue
import logging
import signal
import threading
import asyncio
import time
import collections

# sys.path.append('../../')
#
from copy import copy

import datetime

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
rootPath = os.path.split(rootPath)[0]
os.sys.path.append(rootPath)

import sys
from dquant.constants import Constants
from dquant.markets._binance_spot_ws import BinanceSpotWs
from dquant.markets._huobi_spot_rest import HuobiRest
from dquant.markets._okex_spot_ws_v2 import OkexSpotWs
from dquant.markets._bitfinex_spot_ws import BitfinexSpotWs
from dquant.common.alarms import BlockAlarm
from dquant.common.mongo_conn import MongoConnOrder
from dquant.strategy.tick_data_recorder import Recorder

logger = logging.getLogger('dquant')
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(ch)


class MarketStatus(object):
    # {"Maker": "Bitfinex",
    # "Trade_pair":"eth_btc",
    # "Bitfinex_status": "ok",
    # "Bitfinex_timestamp": 123456789, ...}
    def __init__(self, config_name, target_market, market_dict):
        self.config_name = config_name
        self.config = json.load(open(config_name, 'r'))
        self.strategy_id = self.config["strategy_id"]
        self.trade_pair = self.config["meta_code"]
        self.trade_objs = self.config["trade_obj"]
        self.target_market = target_market
        self.market_dict = market_dict
        # self.trade_pair = self.get_trade_pair()
        self.status = {}
        self.tradeObjinit()
        self.status.update({"Maker": self.target_market, "Trade_pair": self.trade_pair, "strategy_id": self.strategy_id})
        self.reversed_config_map = {'Bitfinex': '1', 'Binance': '2', 'HuoBiPro': '3', 'OKEX': '4'}
        self.target_market_num = self.reversed_config_map[self.target_market]
        self.write_interval = 300
        self.lock = threading.Lock()
        self.client = MongoConnOrder().client
        self.db = self.client.account

        update_status_thread = threading.Thread(target=self.update_status)
        update_status_thread.setDaemon(True)
        update_status_thread.start()


    def tradeObjinit(self):
        logger.debug("trade objs: %s" % self.trade_objs)
        for obj_name, obj in self.trade_objs.items():
            name = obj["depth_name"]
            init_status = obj["trade"]
            status_field = name + "_status"
            self.status.update({status_field: init_status})

    def get_trade_pair(self):
        tp = self.target_market
        try:
            tp = self.config_name.split(".")[0].split("_")[-1]
        except Exception as ex:
            logger.error("MarketStatus: %s" % ex)
        finally:
            return tp

    def update_status(self):
        while True:
            try:
                time.sleep(self.write_interval)
                for mkt_name, mkt_obj in self.market_dict.items():
                    status_field = mkt_name + "_status"
                    status = True if (mkt_obj.status and mkt_obj.available and mkt_obj.latency_good) else False
                    self.status.update({status_field: status})
                self.status.update({"_id": datetime.datetime.utcnow(), 'timestamp': int(time.time() * 1000)})
                self.db.market_status.insert_one(self.status)
            except Exception as ex:
                logger.error("MarketStatus update_status: %s" % ex)


class Audit(object):
    Q_MAKER = queue.Queue()
    Q_MAKER_DELETE = queue.Queue()
    Q_TAKER = queue.Queue()
    def __init__(self, config_name):
        # self.q_maker = queue.Queue()
        # self.q_taker = queue.Queue()
        # self.balance = 0.0
        self.maker_buy_balance = 0.0
        self.maker_sell_balance = 0.0
        # self.dangerous_balance = 10
        self.config = json.load(open(config_name, 'r'))
        self.dangerous_balance = self.config["dangerous_balance"]
        self.audit_reset_interval = self.config["audit_reset_interval"]

        # self.need_block = False
        self.lock = threading.Lock()
        self.holder = threading.Event()
        self.reset_audit_event = threading.Event()

        get_maker_amount_thread = threading.Thread(target=self.get_maker_amount)
        get_maker_amount_thread.setDaemon(True)
        get_maker_amount_thread.start()

        get_taker_amount_thread = threading.Thread(target=self.get_taker_amount)
        get_taker_amount_thread.setDaemon(True)
        get_taker_amount_thread.start()

        get_maker_delete_thread = threading.Thread(target=self.get_maker_delete)
        get_maker_delete_thread.setDaemon(True)
        get_maker_delete_thread.start()

        self.reset_audit_thread(self.reset_audit_event, self.audit_reset_interval)

    def get_maker_amount(self):
        while True:
            try:
                # {side:"buy", amount:0.4}
                m_maker = Audit.Q_MAKER.get()
                logger.debug("m_maker: %s" % m_maker)
                with self.lock:
                    if m_maker["side"] == "buy":
                        self.maker_buy_balance += float(m_maker["amount"])
                    elif m_maker["side"] == "sell":
                        self.maker_sell_balance += float(m_maker["amount"])
            except Exception as ex:
                logger.error("get_maker_amount: %s" % ex)

    def get_taker_amount(self):
        while True:
            try:
                m_taker = Audit.Q_TAKER.get()
                logger.debug("m_taker: %s" % m_taker)
                with self.lock:
                    complex_side = m_taker['side'].lower()
                    simple_side = 'buy' if complex_side.startswith('buy') else 'sell'
                    amount_filled = m_taker['amount_filled']
                    if simple_side == "buy":
                        self.maker_sell_balance -= float(amount_filled)
                    elif simple_side == "sell":
                        self.maker_buy_balance -= float(amount_filled)
            except Exception as ex:
                logger.error("get_maker_amount: %s" % ex)

    def get_maker_delete(self):
        while True:
            try:
                # {'side': side, 'amount_remain': amount_remain}
                m_maker_delete = Audit.Q_MAKER_DELETE.get()
                logger.debug("m_maker_delete: %s" % m_maker_delete)
                with self.lock:
                    side = m_maker_delete['side']
                    amount_remain = m_maker_delete['amount_remain']
                    if side == "buy":
                        self.maker_buy_balance -= float(amount_remain)
                    elif side == "sell":
                        self.maker_sell_balance -= float(amount_remain)
            except Exception as ex:
                logger.error("get_maker_delete: %s" % ex)

    def reset_audit_thread(self, reset_audit_event, seconds):
        self.reset_audit()
        if not reset_audit_event.is_set():
            timerThread = threading.Timer(seconds, self.reset_audit_thread, [reset_audit_event, seconds])
            timerThread.setDaemon(True)
            timerThread.start()

    def reset_audit(self):
        with self.lock:
            pass
            # self.maker_buy_balance = 0
            # self.maker_sell_balance = 0
        logger.info("Audit Reset")

    def check(self):
        logger.debug('maker balance: %s, %s' % (self.maker_buy_balance, self.maker_sell_balance))
        if abs(self.maker_buy_balance) >= self.dangerous_balance or abs(self.maker_sell_balance) >= self.dangerous_balance:
            logger.error("Audit: Hold on!")
            self.holder.clear()
            self.holder.wait()

    def need_to_hold(self):
        logger.info('maker balance: %s, %s' % (self.maker_buy_balance, self.maker_sell_balance))
        if abs(self.maker_buy_balance) >= self.dangerous_balance or abs(
                self.maker_sell_balance) >= self.dangerous_balance:
            logger.error("Audit: Hold on!")
            return True
        else:
            return False
        # if Profit.LOSS:
        #     logger.error("Audit: This process is at LOSS! Pls check")
        #     self.holder.clear()
        #     self.holder.wait()


class DynamicThres(object):
    DEAL_COUNT = 0
    THRES = 0.0
    MIN_THRES = 0.0
    MAX_THRES = 0.0
    ORIG_THRES = 0.0
    ORIG_MIN_THRES = 0.0
    ORIG_MAX_THRES = 0.0
    # 阈值变动范围是50%-150%
    LOWER_COUNT = 0 # 下降次数，最大5次
    UPPER_COUNT = 0 # 上升次数，最大5次
    LOCK = threading.Lock()
    ORIG_TRADE_AMOUNT = 0.0
    TRADE_AMOUNT = 0.0
    # 交易量上升次数（变动范围是100%-150%）
    TRADE_AMOUNT_UPPER_COUNT = 0
    def __init__(self, target_market, config_file):
        self.started = False
        # self.deal_count = 0
        # self.start_time = 0
        self.c = 0
        self.dynamic_thres_event = threading.Event()
        self.q = queue.Queue()
        # self.lock = threading.Lock()
        self.client = MongoConnOrder().client
        self.db = self.client.account
        self.target_market = target_market
        self.config = json.load(open(config_file, 'r'))
        self.strategy_id = self.config["strategy_id"]
        self.trade_pair = self.config["meta_code"]

        self.store_thread = threading.Thread(target=self.thres_store)
        self.store_thread.setDaemon(True)
        self.store_thread.start()

    @classmethod
    def load_thres(cls, thres, min_thres, max_thres, initial_amount):
        with DynamicThres.LOCK:
            DynamicThres.THRES = thres
            DynamicThres.MIN_THRES = min_thres
            DynamicThres.MAX_THRES = max_thres
            DynamicThres.TRADE_AMOUNT = initial_amount
            DynamicThres.ORIG_THRES = thres
            DynamicThres.ORIG_MIN_THRES = min_thres
            DynamicThres.ORIG_MAX_THRES = max_thres
            DynamicThres.ORIG_TRADE_AMOUNT = initial_amount


    @classmethod
    def get_thres(cls):
        return DynamicThres.THRES, DynamicThres.MIN_THRES, DynamicThres.MAX_THRES, DynamicThres.TRADE_AMOUNT

    @classmethod
    def reset_timer(cls):
        with DynamicThres.LOCK:
            DynamicThres.DEAL_COUNT = 0

    @classmethod
    def deal(cls):
        with DynamicThres.LOCK:
            DynamicThres.DEAL_COUNT += 1


    def start_timer(self):
        if not self.started:
            self.started = True
            # self.start_time = time.time()
            # time.sleep(60)
            self.dynamic_thres_thread(self.dynamic_thres_event, 60)

    def assert_thres(self):
        assert DynamicThres.THRES > 0, "thres lower than 0"
        assert DynamicThres.MIN_THRES > 0, "min_thres lower than 0"
        assert DynamicThres.MAX_THRES > 0, "max_thres lower than 0"

    def dynamic_thres_thread(self, dynamic_thres_event, seconds):
        if self.c:
            self.dynamic_thres()
            self.reset_timer()
        else:
            self.q.put([DynamicThres.THRES, DynamicThres.MIN_THRES, DynamicThres.MAX_THRES, DynamicThres.DEAL_COUNT])
        if not dynamic_thres_event.is_set():
            timerThread = threading.Timer(seconds, self.dynamic_thres_thread, [dynamic_thres_event, seconds])
            timerThread.setDaemon(True)
            timerThread.start()
            self.c += 1

    def dynamic_thres(self):
        # mow = time.time()
        self.assert_thres()
        if DynamicThres.DEAL_COUNT == 0 and DynamicThres.LOWER_COUNT < 5:
            with DynamicThres.LOCK:
                DynamicThres.THRES -= DynamicThres.ORIG_THRES * 0.1
                DynamicThres.MIN_THRES -= DynamicThres.ORIG_MIN_THRES * 0.1
                DynamicThres.MAX_THRES -= DynamicThres.ORIG_MAX_THRES * 0.1
                DynamicThres.LOWER_COUNT += 1
                DynamicThres.UPPER_COUNT -= 1

        if DynamicThres.DEAL_COUNT >= 5 and DynamicThres.UPPER_COUNT < 5:
            with DynamicThres.LOCK:
                DynamicThres.THRES += DynamicThres.ORIG_THRES * 0.1
                DynamicThres.MIN_THRES += DynamicThres.ORIG_MIN_THRES * 0.1
                DynamicThres.MAX_THRES += DynamicThres.ORIG_MAX_THRES * 0.1
                DynamicThres.UPPER_COUNT += 1
                DynamicThres.LOWER_COUNT -= 1

        if DynamicThres.DEAL_COUNT >= 5 and DynamicThres.TRADE_AMOUNT_UPPER_COUNT < 5:
            with DynamicThres.LOCK:
                DynamicThres.TRADE_AMOUNT += DynamicThres.ORIG_TRADE_AMOUNT * 0.1
                DynamicThres.TRADE_AMOUNT_UPPER_COUNT += 1

        if DynamicThres.DEAL_COUNT == 0 and DynamicThres.TRADE_AMOUNT_UPPER_COUNT > 0:
            with DynamicThres.LOCK:
                DynamicThres.TRADE_AMOUNT -= DynamicThres.ORIG_TRADE_AMOUNT * 0.1
                DynamicThres.TRADE_AMOUNT_UPPER_COUNT -= 1

        # self.started = False
        self.q.put([DynamicThres.THRES, DynamicThres.MIN_THRES, DynamicThres.MAX_THRES, DynamicThres.DEAL_COUNT, DynamicThres.TRADE_AMOUNT])
        logger.debug("dynamic_thres %s, %s, %s, %s. Count: %s, %s, %s" % (DynamicThres.THRES,
                                                                          DynamicThres.MIN_THRES,
                                                                          DynamicThres.MAX_THRES,
                                                                          DynamicThres.TRADE_AMOUNT,
                                                                          DynamicThres.LOWER_COUNT,
                                                                          DynamicThres.UPPER_COUNT,
                                                                          DynamicThres.TRADE_AMOUNT_UPPER_COUNT))

    def thres_store(self):
        while True:
            try:
                m = self.q.get()
                data = {"thres": m[0], "min_thres": m[1], "max_thres": m[2], "deal_count": m[3], "amount": m[4], "timestamp": int(time.time()*1000),
                        "maker": self.target_market, "trade_pair": self.trade_pair, "_id": datetime.datetime.utcnow(), "strategy_id": self.strategy_id}
                self.db.thres.insert_one(data)
            except Exception as ex:
                logger.error("thres_store: %s" % ex)


class Profit(threading.Thread):
    Q_PROF = queue.Queue()
    LOSS = {}
    def __init__(self, config_name, target_market):
        super().__init__()
        self.client = MongoConnOrder().client
        self.db = self.client.account
        self.config = json.load(open(config_name, 'r'))
        self.trade_pair = self.config["meta_code"]
        self.target_market = target_market
        # self.past_10_orders = []
        self.past_10_orders = {}

    def _put_into_past(self, d):
        taker = d["taker"]
        if d["taker"] not in self.past_10_orders:
            self.past_10_orders[taker] = [d]
        else:
            self.past_10_orders[taker].append(d)
        if len(self.past_10_orders[taker]) > 10:
            self.past_10_orders[taker].pop(0)

    def _calc_past_10_orders_profit(self, taker):
        total_prof = 0.0
        for order in self.past_10_orders[taker]:
            total_prof += order["net_profit"]
        if total_prof < 0:
            if not Profit.LOSS[taker]:
                timerThread = threading.Timer(interval=1800, function=self.reset_profit, args=(taker, ))
                timerThread.setDaemon(True)
                timerThread.start()
            logger.error("taker %s is at loss" % taker)
            Profit.LOSS[taker] = True

    def reset_profit(self, mkt):
        Profit.LOSS[mkt] = False
        logger.info("Profit Reset")

    def run(self):
        while True:
            try:
                m = Profit.Q_PROF.get()
                # total_fee = m["maker_fee"] + m["taker_fee"]
                if m['maker_side'] == "buy":
                    # maker 手续费以target计算
                    maker_vol = m['maker_amount'] * m['maker_price'] * (1 + m["maker_fee"])
                    # taker 手续费以base计算，这里用近似的来代替
                    taker_vol = m['taker_amount'] * m['taker_price'] * (1 - m["taker_fee"])
                    net_profit = taker_vol - maker_vol
                else:
                    # maker 手续费以base计算，这里用近似的来代替
                    maker_vol = m['maker_amount'] * m['maker_price'] * (1 - m["maker_fee"])
                    # taker 手续费以target计算
                    taker_vol = m['taker_amount'] * m['taker_price'] * (1 + m["taker_fee"])
                    net_profit = maker_vol - taker_vol
                m.update({"net_profit": net_profit,
                          "trade_pair": self.trade_pair,
                          "maker": self.target_market})
                self._put_into_past(m)
                if len(self.past_10_orders[m["taker"]]) >= 10:
                    self._calc_past_10_orders_profit(m["taker"])
                self.db.profit.insert_one(m)
            except Exception as ex:
                logger.error("Profit: %s" % ex)

class TakersWs(threading.Thread):
    def __init__(self, mkt, meta_code, strategy_id, config_name):
        super(TakersWs, self).__init__()
        new = asyncio.new_event_loop()
        asyncio.set_event_loop(new)
        self.mkt = mkt(meta_code, loop=new)
        self.mkt.strategy_id = strategy_id
        self.mkt.isTaker = True
        self.base_coin = self.mkt.base_currency
        self.target_coin = self.mkt.market_currency
        self.minimum_amount = self.mkt.minimum_amount
        self.name = self.mkt.name
        self.fee_rate = self.mkt.fee_rate
        self.fee_rate_taker = self.mkt.fee_rate_taker
        self.q = queue.Queue()
        self.mkt.setDaemon(True)
        self.mkt.start()
        self.c = 0
        self.error_c = 0
        self.accumulative_amount = {'buy': 0, 'sell': 0}
        # 列队状态
        self.status = True
        # 交易所状态 是否可用
        self.available = True
        # 是否在最大误差内
        self.within_amount_error = True
        self.config = json.load(open(config_name, 'r'))
        self.max_task_on_do = self.config["max_task_on_do"]
        self.wake_interval = self.config["taker_wake_interval"]
        self.max_amount_unfilled = self.config["max_amount_unfilled"]
        self.taker_holder = threading.Event()
        self.taker_holder.set()
        # 连续尝试唤醒次数
        self.check_alive_times = 0
        self.amount_lock = threading.Lock()
        self.wallet_lock = threading.Lock()
        self.active_orders = {'buy':{}, 'sell':{}}
        # self.amount_monitor = {'buy':0, 'sell':0}
        self.amount_ash = 0
        self.abandoned_orders = []
        self.wallet = {}
        self.prof = {}
        self.q_prof = queue.Queue()
        self.prof_lock = threading.Lock()
        self.status_lock = threading.Lock()

        order_result_collector_thread = threading.Thread(target=self.order_result_collector)
        order_result_collector_thread.setDaemon(True)
        order_result_collector_thread.start()

        get_account_thread = threading.Thread(target=self.getAccountThread)
        get_account_thread.setDaemon(True)
        get_account_thread.start()

        check_task_on_do_thread = threading.Thread(target=self.check_task_on_do)
        check_task_on_do_thread.setDaemon(True)
        check_task_on_do_thread.start()

    @property
    def latency_good(self):
        return self.mkt.latency_good

    def check_amount_unfilled(self):
        try:
            temp_active_orders = copy(self.active_orders)
            for each_side, orders in temp_active_orders.items():
                if not orders:
                    continue
                unfilled_amount = 0
                for order_id, amount_to_be_filled in orders.items():
                    unfilled_amount += amount_to_be_filled
                if abs(unfilled_amount) >= self.max_amount_unfilled:
                    logger.error("Taker %s unfilled amount: %s, status=False" % (self.name, unfilled_amount))
                    with self.status_lock:
                        # 通知外部不要调用
                        self.status = False
                        # 通知内部误差状态，检查时不要恢复
                        self.within_amount_error = False
                # 如果回到误差内，改回状态
                elif not self.within_amount_error:
                    with self.status_lock:
                        self.within_amount_error = True
        except Exception as ex:
            logger.error("check_amount_unfilled: %s" % ex)

    def order_result_collector(self):
        while True:
            '''
            order_data = {'order_id': order_id, 'side': side, 'trade_pair': trade_pair, 'price': price,
            'amount_filled': amount_filled, 'order_time': time_stamp, 'account_id': client_order_id,
            'platform_id': platform_name,'strategy_id': strategy_id,  platform_id_field: platform_account_id}
            order_data.update({"_id": datetime.datetime.utcnow(), 'timestamp': int(time.time() * 1000), 'ip': ip, 'pid':pid,
            })
            '''
            order_result = self.mkt.q_taker_order_result.get()
            logger.debug("order_result_collector get: %s" % order_result)
            order_id = int(order_result['order_id'])
            complex_side = order_result['side'].lower()
            # 必须是buy或sell开头
            if not complex_side.startswith("buy") and not complex_side.startswith("sell"):
                logger.debug("Taker %s Unknown order type: %s" % (self.name, order_result))
                continue
            simple_side = 'buy' if complex_side.startswith('buy') else 'sell'
            amount_filled = order_result['amount_filled']
            if order_id in self.active_orders[simple_side]:
                Audit.Q_TAKER.put(order_result)
                with self.amount_lock:
                    try:
                        amount_to_be_filled = self.active_orders[simple_side][order_id]
                        # 买的少了为正，卖的少了为负
                        if simple_side is 'buy':
                            self.amount_ash += amount_to_be_filled - amount_filled
                        else:
                            self.amount_ash -= amount_to_be_filled - amount_filled
                        del self.active_orders[simple_side][order_id]
                        # for each_side, orders in self.active_orders.items():
                        #     if not orders:
                        #         continue
                        #     unfilled_amount = 0
                        #     for order_id, amount_to_be_filled in orders.items():
                        #         unfilled_amount += amount_to_be_filled
                        #     if unfilled_amount >= self.max_amount_unfilled:
                        #         logger.error("Taker %s unfilled amount: %s, status=False" % (self.name, unfilled_amount))
                        #         with self.status_lock:
                        #             self.status = False
                        if self.amount_ash > 0.01:      # 少买超过0.01个, 补卖单的时候多买一点
                            pass
                            # self.accumulative_amount['sell'] += self.amount_ash
                            # self.amount_ash = 0
                        elif self.amount_ash < -0.01:   # 少卖超过0.01个, 补买单的时候多卖一点
                            pass
                            # self.accumulative_amount['buy'] += abs(self.amount_ash)
                            # self.amount_ash = 0
                    except Exception as ex:
                        logger.error("order_result_collector: %s, %s" % (ex, order_result))
                if order_id in self.prof:
                    with self.prof_lock:
                        prof_data = self.prof.pop(order_id)
                        prof_data.update({"taker_amount": amount_filled,
                                          "taker_price": order_result.get("price", 0.0),
                                          "taker_side": simple_side,
                                          "taker_order_id": order_id,
                                          "strategy_id": order_result.get("strategy_id", ""),
                                          "timestamp": int(time.time() * 1000)})
                        Profit.Q_PROF.put(prof_data)
            else:
                self.abandoned_orders.append(order_result)

            self.find_in_abandoned_order(simple_side)
            # abandoned_order_collect = []
            # for abandoned_order in self.abandoned_orders:
            #     if abandoned_order["order_id"] in self.active_orders[simple_side]:
            #         self.mkt.q_taker_order_result.put(abandoned_order)
            #         abandoned_order_collect.append(abandoned_order)
            # for abandoned_order_collected in abandoned_order_collect:
            #     self.abandoned_orders.remove(abandoned_order_collected)
            logger.debug("Taker %s - active_orders:%s; accumulative_amount: %s; abandoned_order: %s" % (self.name, self.active_orders, self.accumulative_amount, self.abandoned_orders))


    def find_in_abandoned_order(self, simple_side):
        with self.amount_lock:
            abandoned_order_collect = []
            for abandoned_order in self.abandoned_orders:
                if abandoned_order["order_id"] in self.active_orders[simple_side]:
                    self.mkt.q_taker_order_result.put(abandoned_order)
                    abandoned_order_collect.append(abandoned_order)
            for abandoned_order_collected in abandoned_order_collect:
                self.abandoned_orders.remove(abandoned_order_collected)



    # 在taker状态available=False时触发的定时任务
    def check_alive(self):
        # 如果已经连续触发5次，不再唤醒。否则会产生大量短信报警
        # check_alive_times 只在列队补单数小于5才会被清零
        if self.check_alive_times >= 5:
            return None
        logger.info("Trying to wake up taker %s" % self.name)
        self.check_alive_times += 1
        # taker列队正常，列队中没有待补单
        if self.status and self.q.qsize() == 0:
            self.available = True
        # taker列队报错五次退出，并且已经处于阻塞状态
        elif not self.status and not self.taker_holder.is_set():
            # 取消阻塞状态，如果列队中有待补单，则会调用check_task_on_do。继续补单，直到小于5
            self.taker_holder.set()
            time.sleep(5)
            self.available = True

    def check_alive_thread(self, interval):
        timerThread = threading.Timer(interval=interval, function=self.check_alive)
        timerThread.setDaemon(True)
        timerThread.start()

    def check_task_on_do(self):
        while True:
            try:
                task_on_do = self.q.qsize() + self.c
                if task_on_do >= self.max_task_on_do:
                    logger.warning('Taker(%s) task on do: %s' % (self.name, task_on_do))
                    with self.status_lock:
                        self.status = False
                elif not self.status and self.taker_holder.is_set() and self.within_amount_error:
                    logger.warning('Taker(%s) status reset to True' % self.name)
                    with self.status_lock:
                        self.status = True
                self.check_amount_unfilled()
            except Exception as ex:
                logger.error("Taker %s check_task_on_do: %s" % (self.name, ex))
            finally:
                time.sleep(1)

    def getAccount(self):
        with self.wallet_lock:
            ret = copy(self.wallet)
        return ret

    def getAccountThread(self):
        while True:
            if self.available:
                balance = self.updateAccount(coin=[self.base_coin, self.target_coin])
                if balance:
                    with self.wallet_lock:
                        self.wallet.update(balance)
            time.sleep(1)

    def updateAccount(self, coin):
        try:
            account = self.mkt.getAccount(coin=coin)
        except TimeoutError as ex:
            self.available = False
            try:
                t = ex.args
                seconds = t[0] if (t and t[0]) else self.wake_interval
                logger.info("Taker %s will be wake up %s seconds later" % (self.name, seconds))
                self.check_alive_thread(seconds)
            except Exception as ex:
                logger.error("Taker getAccount: %s" % ex)
            finally:
                return None

        if 'exchange' in account:
            return account['exchange']
        return account

    def getDepth(self):
        try:
            depth = self.mkt.getDepth()
            return depth
        except TimeoutError as ex:
            self.available = False
            try:
                t = ex.args
                seconds = t[0] if (t and t[0]) else self.wake_interval
                logger.info("Taker %s will be wake up %s seconds later" % (self.name, seconds))
                self.check_alive_thread(seconds)
            except Exception as ex:
                logger.error("Taker getDepth: %s" % ex)
            finally:
                return None

    def parse_meta(self, meta_code):
        self.mkt.parse_meta(meta_code)

    def mkt_buy(self, amount_to_be_filled, reference_price):
        '''
        :param amount_to_be_filled: amount that need to be filled
        :param reference_price: for some exchanges(OKEX), market-buy require the arg 'price' therefore amount needs to be converted to price
        :return:
        '''
        res = self.mkt.buy(amount_to_be_filled)
        return res

    def mkt_sell(self, amount_to_be_filled):
        res = self.mkt.sell(amount_to_be_filled)
        return res

    def calc_amount_in_queue(self):
        # 会导出列队里的全部内容
        total = 0
        if self.q.qsize() > 0:
            while True:
                try:
                    m = self.q.get()
                    side = m.get('side')
                    if side == "buy":
                        total += m['amount_to_be_filled']
                    elif side == "sell":
                        total -= m['amount_to_be_filled']
                    if self.q.qsize() == 0:
                        break
                except Exception as ex:
                    logger.error("calc_amount_in_queue: %s" % ex)
        total += self.accumulative_amount["buy"]
        total -= self.accumulative_amount["sell"]
        with self.amount_lock:
            self.accumulative_amount["buy"] = 0
            self.accumulative_amount["sell"] = 0
        logger.info("calc_amount_in_queue result: %s" % total)
        return total

    def run(self):
        while True:
            # self.check_task_on_do()
            '''
            "maker_fee": self.mkt[self.target_mkt].fee_rate, "taker_fee": self.mkt[taker_market].fee_rate_taker
            '''
            m = self.q.get()
            logger.info("Taker get message from maker: %s " % m)
            # print(m)
            maker_order_id = m.get('order_id', 0)
            side = m.get('side')
            taker_side = None
            with self.amount_lock:
                amount_to_be_filled = m['amount_to_be_filled'] + self.accumulative_amount[side]
            reference_price = m.get('reference_price', None)
            if amount_to_be_filled >= self.minimum_amount:
                logger.info('Taker(%s) get task: %s, real amount: %s' % (self.name, m, amount_to_be_filled))
                self.c += 1
                try:
                    result = None
                    # 补单
                    if side == 'buy':
                        result = self.mkt_sell(amount_to_be_filled=amount_to_be_filled)
                        if 'order_id' in result:
                            order_id = int(result['order_id'])
                            with self.amount_lock:
                                taker_side = "sell"
                                self.active_orders[taker_side][order_id] = amount_to_be_filled
                            with self.prof_lock:
                                self.prof[order_id] = {"maker_amount": amount_to_be_filled,
                                                       "maker_price": m.get('price', 0.0),
                                                       "maker_side": side,
                                                       "maker_order_id": maker_order_id,
                                                       "maker_fee": m.get('maker_fee', 0.0),
                                                       "taker_fee": m.get('taker_fee', 0.0),
                                                       "taker": self.name
                                                       }
                    if side == 'sell':
                        result = self.mkt_buy(amount_to_be_filled=amount_to_be_filled, reference_price=reference_price)
                        if 'order_id' in result:
                            order_id = int(result['order_id'])
                            with self.amount_lock:
                                taker_side = "buy"
                                self.active_orders[taker_side][order_id] = amount_to_be_filled
                            with self.prof_lock:
                                self.prof[order_id] = {"maker_amount": amount_to_be_filled,
                                                       "maker_price": m.get('price', 0.0),
                                                       "maker_side": side,
                                                       "maker_order_id": maker_order_id,
                                                       "maker_fee": m.get('maker_fee', 0.0),
                                                       "taker_fee": m.get('taker_fee', 0.0),
                                                       "taker": self.name
                                                       }
                    # logger.debug(result)
                    # self.mkt[self.hist[order_id]].q.put(m)
                    if not result or ('status' in result and not result['status']):
                        logger.error("Taker error: %s failed to buy/sell (%s), Retry" % (self.name, m))
                        action = "taker_{}_fail".format(taker_side)
                        Recorder.record(action, amount=amount_to_be_filled, taker_task_order_id=maker_order_id, taker_platform=self.name)
                        self.error_c += 1
                        self.q.put(m)
                    else:
                        logger.info('Taker(%s) task done: %s' % (self.name, result))
                        if taker_side:
                            self.find_in_abandoned_order(taker_side)
                            action = "taker_{}".format(taker_side)
                            Recorder.record(action, amount=amount_to_be_filled, order_id=int(result['order_id']), taker_task_order_id=maker_order_id, taker_platform=self.name)
                        # 不需要清零
                        # self.error_c = 0
                        with self.amount_lock:
                            self.accumulative_amount[side] = 0
                        self.check_alive_times = 0

                except Exception as ex:
                    logger.error("Taker error: %s (order details %s, info: %s)" % (self.name, m, ex))
                    self.error_c += 1
                    self.q.put(m)
                finally:
                    self.c -= 1
                    # 某个Taker报错超过5次
                    if self.error_c >= 5:
                        logger.critical("Fatal Error: Taker %s seems not working properly, exit" % self.name)
                        with self.status_lock:
                            self.status = False
                        self.taker_holder.clear()
                        self.taker_holder.wait()
                        # break
            # 待交易量不满足交易所最小交易额度
            else:
                self.accumulative_amount[side] += m['amount_to_be_filled']


class BitfinexTaker(TakersWs):
    def __init__(self, meta_code, strategy_id, config_name):
        super(BitfinexTaker, self).__init__(BitfinexSpotWs, meta_code, strategy_id, config_name=config_name)


class BinanceTaker(TakersWs):
    def __init__(self, meta_code, strategy_id, config_name):
        super(BinanceTaker, self).__init__(BinanceSpotWs, meta_code, strategy_id, config_name=config_name)

    def mkt_buy(self, amount_to_be_filled, reference_price):
        '''
        :param amount_to_be_filled: amount that need to be filled
        :param reference_price: for some exchanges(OKEX), market-buy require the arg 'price' therefore amount needs to be converted to price
        :return:
        '''
        res = self.mkt.buy(amount=amount_to_be_filled)
        return res

    def mkt_sell(self, amount_to_be_filled):
        res = self.mkt.sell(amount=amount_to_be_filled)
        return res


class HuobiTaker(TakersWs):
    def __init__(self, meta_code, strategy_id, config_name):
        super(HuobiTaker, self).__init__(HuobiRest, meta_code, strategy_id, config_name=config_name)

    def mkt_buy(self, amount_to_be_filled, reference_price):
        res = self.mkt.buy(amount=amount_to_be_filled*reference_price)
        return res

    def mkt_sell(self, amount_to_be_filled):
        res = self.mkt.sell(amount=amount_to_be_filled)
        return res


class OkexWsTaker(TakersWs):
    def __init__(self, meta_code, strategy_id, config_name):
        super(OkexWsTaker, self).__init__(OkexSpotWs, meta_code, strategy_id, config_name=config_name)

    def mkt_buy(self, amount_to_be_filled, reference_price):
        res = self.mkt.buy(price=amount_to_be_filled*reference_price)
        return res


class TargetMargetWs(threading.Thread):
    def __init__(self, mkt, meta_code, strategy_id):
        super(TargetMargetWs, self).__init__()
        # os.environ[Constants.DQUANT_ENV] = "dev"
        self.new = asyncio.new_event_loop()
        asyncio.set_event_loop(self.new)
        self.t_mkt = mkt(meta_code, self.new)
        self.t_mkt.strategy_id =strategy_id
        self.target_coin = self.t_mkt.market_currency
        self.base_coin = self.t_mkt.base_currency
        self.fee_rate = self.t_mkt.fee_rate
        # self.minimun_amount = self.t_mkt.minimum_amount
        self.t_mkt.order_result_required = True
        self.t_mkt.setDaemon(True)
        self.t_mkt.start()
        self.q_order_result = self.t_mkt.q_order_result
        self.q = queue.Queue()
        self.q_output = queue.Queue()
        # 仓位
        self.lastPosition = {'buy': {}, 'sell': {}}
        self.last_get_order_info={'buy':{'ordid':None, 'amount_filled': None}, 'sell':{'ordid':None, 'amount_filled': None}}
        self.status = True
        self.available = True
        self.wallet_lock = threading.Lock()
        self.wallet = {}
        self.name = self.t_mkt.name

        get_account_thread = threading.Thread(target=self.getAccountThread)
        get_account_thread.setDaemon(True)
        get_account_thread.start()

    @property
    def latency_good(self):
        return self.t_mkt.latency_good

    def mkt_buy(self, amount_to_be_filled, reference_price):
        '''
        :param amount_to_be_filled: amount that need to be filled
        :param reference_price: for some exchanges(OKEX), market-buy require the arg 'price' therefore amount needs to be converted to price
        :return:
        '''
        res = self.t_mkt.buy(amount_to_be_filled)
        return res

    def mkt_sell(self, amount_to_be_filled, reference_price):
        res = self.t_mkt.sell(amount_to_be_filled)
        return res

    def account_format(self,account):
        account_str = ''
        for c, a in account.items():
            account_str += str(a)+str(c) + ' '
        return account_str

    def getDepth(self):
        while True:
            try:
                return self.t_mkt.getDepth()
            except TimeoutError:
                logger.error('Target Market getDepth timeout, Retry')
                continue

    def getAccount(self):
        with self.wallet_lock:
            ret = copy(self.wallet)
        return ret

    def getAccountThread(self):
        while True:
            if self.available:
                balance = self.updateAccount(coin=[self.base_coin, self.target_coin])
                if balance:
                    with self.wallet_lock:
                        self.wallet.update(balance)
            time.sleep(1)

    def updateAccount(self, coin):
        while True:
            try:
                account = self.t_mkt.getAccount(coin=coin)
                break
            except TimeoutError:
                logger.error('Target Market getAccount timeout, Retry')
                continue
        if 'exchange' in account:
            return account['exchange']
        return account

    # 返回最后一个买/卖/删除记录，因为getorder不会记录已经成交或者删除的订单信息,而已经执行的订单保存在bfx.getHist里（只保存最近10个）
    def get_latest_order(self, side=None, order_id=None):
        # 查询买卖订单
        if side and order_id:
            hist = self.t_mkt.getHist(side=side, order_id=order_id)
            return hist
        else:
            return {'status': False}
        # else:
        #     hist = self.bfx.getHist()
        #     temp_hist = copy(hist)
        #     # 从最近成交/成功删除的订单开始遍历
        #     if temp_hist[side]:
        #         latest_order_id, latest_order_details = temp_hist[side].popitem()
        #         return {'ordid': latest_order_id, 'details': latest_order_details}
        #     else:
        #         return None


    def my_getOrder(self, order_id=None):
        # 初始化返回结果
        # initial_info = {'ordid': None, 'price': None, 'amount_remain': None, 'amount_orig': None}
        ret = {'buy': {'ordid': None, 'price': None, 'amount_remain': None, 'amount_orig': None},
               'sell': {'ordid': None, 'price': None, 'amount_remain': None, 'amount_orig': None}}
        order_snapshot = []
        if order_id:
            temp_order_id = copy(order_id)
            for side, id in temp_order_id.items():
                order_details = self.t_mkt.getOrder(id)
                # print(order_details)
                # if order_details:
                #     order_snapshot[id] = order_details
                if order_details['status'] is True:
                    order_snapshot.append(order_details)
        else:
            try:
                order_snapshot = self.t_mkt.getAllOrders()
            except:
                pass
        # print('temp_order_snapshot', order_snapshot)
        if order_snapshot:
            for order_details in order_snapshot:
                amount_remain = order_details['amount_remain']        # 剩余未成交的数量, 正买负卖.若完全成交为None
                amount_orig = order_details['amount_orig']
                side = order_details['side']
                price = order_details['price']
                ret[side] = {'ordid': order_details['order_id'], 'price': price, 'amount_remain': amount_remain, 'amount_orig': amount_orig}
        return ret

    def trade_back(self, amount_to_trade_back, initial_amount, reference_price):
        trade_back = {"buy": self.mkt_buy, "sell": self.mkt_sell}
        amount_remain = amount_to_trade_back
        side = "sell" if amount_remain > 0 else "buy"
        amount_remain = abs(amount_remain)
        while True:
            if amount_remain - initial_amount >= initial_amount:
                trade_amount = initial_amount
            else:
                trade_amount = amount_remain
            result = trade_back[side](amount_to_be_filled=trade_amount, reference_price=reference_price)
            logger.info("trade_back: remain: %s, amount: %s" % (amount_remain, trade_amount))
            action = "maker_{}_trade_back"
            order_id = 0
            if result:
                order_id = result.get("order_id", 0)
            Recorder.record(action, amount=trade_amount, order_id=order_id)
            amount_remain -= trade_amount

            if amount_remain <= 0:
                logger.info("trade_back: Done.")
                break

    def run(self):
        while True:
            m = self.q.get()
            # logger.debug(m)
            if m['type'] == 'New order':
                price = m['price']
                side = m['side']
                amount = m['amount']
                name = m.get('name', None)
                if side == 'buy':
                    result = self.t_mkt.buy(amount=amount, price=price)
                else:
                    result = self.t_mkt.sell(amount=amount, price=price)
                Audit.Q_MAKER.put({"amount": amount, "side": side})
                # print(result)
                if not result:
                    m = {'type': 'Order new',
                         'order_id': None,
                         'amount': None,
                         'name': name}
                    action = "maker_{}_fail".format(side)
                    Recorder.record(action, amount=amount, price=price, taker_platform=name)

                elif 'order_id' in result:
                    # 乱序返回信息，有可能无法getOrder
                    if self.name == "Bitfinex":
                        order_details = result
                    else:
                        order_details = self.t_mkt.getOrder(result['order_id'])
                    if order_details['status']:
                        m = {'type': 'Order new',
                             'order_id': order_details['order_id'],
                             'amount': order_details['amount_orig'],
                             'name': name}
                        action = "maker_{}".format(side)
                        Recorder.record(action, amount=amount, price=price, order_id=order_details['order_id'], taker_platform=name)
                    else:
                        m = {'type': 'Order new',
                             'order_id': result['order_id'],
                             'amount': result.get('amount_orig', amount),
                             'name': name}
                        action = "maker_{}".format(side)
                        Recorder.record(action, amount=amount, price=price, order_id=result['order_id'], taker_platform=name)
                else:
                    logger.error('t_mkt buy: %s' % result)

                self.q_output.put(m)

            elif m['type'] == 'Get buy and sell orders':
                order_id = m.get('order_id', None)
                name = m.get('name', None)
                ret = self.my_getOrder(order_id)
                # print('Get buy and sell orders', ret)
                amount_filled = None
                for side, details in ret.items():
                    amount_remain = details['amount_remain']
                    amount_orig = details['amount_orig']

                    if amount_remain:
                        amount_filled = abs(amount_orig - amount_remain)
                        self.lastPosition[side][order_id.get(side, None)] = amount_remain
                        logger.info('GetOrder(to %s): id %s, filled: %s' % (name, details['ordid'], amount_filled))
                    # 如果卖/卖位置的订单已经被删除，则amount_remain=None，表示上一个订单已经完全成交(包括极端情况)
                    else:
                        try:
                            latest_executed_order = self.get_latest_order(side=side, order_id=order_id.get(side, None))
                            # print('latest_executed_order',latest_executed_order)
                            if not latest_executed_order['status']:
                                ret[side] = {'ordid': None, 'price':None, 'details': None, 'amount_remain':None, 'amount_orig':None, 'amount_filled':None}
                                continue
                            self.lastPosition[side][order_id.get(side, None)] = amount_remain
                            logger.info('GetOrder(to %s): id %s, filled: %s (from hist)' % (name, latest_executed_order['order_id'], latest_executed_order['amount_filled']))
                            ret[side]['price'] = None
                            ret[side]['amount_remain'] = None
                        except Exception as ex:
                            ret[side]['price'] = None
                            ret[side]['amount_remain'] = None
                            logger.error('Get buy and sell orders(to %s): %s' % (name, ex))

                    # ret[side]['amount_filled'] = amount_filled
                ret['name'] = name
                # print(ret)
                self.q_output.put(ret)

            elif m['type'] == 'Delete and place new order':
                order_id = m.get('order_id', None)
                ret = self.my_getOrder(order_id)
                # print('Delete and place new order', ret)
                #   待下单信息
                side = m['side']
                amount = m['amount']
                price = m['price']
                name = m.get('name', None)
                # 待删除订单信息
                ordid = ret[side]['ordid']
                old_price = ret[side]['price']
                amount_orig = 0
                amount_remain =0
                # 删除订单
                # 订单状态未完成（可以查到订单号）
                if ordid:
                    result = self.t_mkt.deleteOrder(ordid)
                    # print(result)
                    amount_remain = result['amount_remain']
                    amount_orig = result['amount_orig']
                    # 删除订单中有未成交的amount_remain,输出未成交的数量到屏幕
                    if result['status']:
                        amount_filled = result['amount_filled']
                        logger.info('Delete: canceling order %s @%s, filled %s, last position: %s' % (ordid, old_price, amount_filled, self.lastPosition[side][ordid]))
                        self.lastPosition[side][ordid] = amount_remain
                    # 删除过程中成交了
                    else:
                        try:
                            last_executed_order = self.get_latest_order(side=side, order_id=order_id[side])
                            amount_remain = last_executed_order['amount_remain'] if last_executed_order['amount_remain'] else 0 # 正常情况下是0
                            amount_filled = last_executed_order['amount_filled']
                            amount_orig = last_executed_order['amount_orig']
                            self.lastPosition[side][order_id[side]] = amount_remain
                            logger.info('Delete: id %s has been filled before deleted, amount: %s ' % (last_executed_order['order_id'], amount_filled))
                            logger.info('Delete: canceling order %s @%s remaining %s' % (ordid, old_price, amount_remain))
                        except Exception as ex:
                            logger.error(ex)
                # 订单已完成
                else:
                    try:
                        last_deleted_order = self.get_latest_order(side=side, order_id=order_id[side])
                        amount_remain = last_deleted_order['amount_remain']  # 正常情况下是0
                        amount_filled = last_deleted_order['amount_filled']
                        amount_orig = last_deleted_order['amount_orig']
                        self.lastPosition[side][order_id[side]] = amount_remain
                        logger.info('Delete: id %s has been filled before deleted, amount: %s ' % (last_deleted_order['order_id'], amount_filled))
                    except Exception as ex:
                        logger.error(ex)
                try:
                    if not self.lastPosition[side][order_id[side]]:
                        del self.lastPosition[side][order_id[side]]
                except:
                    pass
                action = "maker_delete"
                Recorder.record(action, amount=amount_remain, order_id=ordid, taker_platform=name)
                if amount_remain:
                    Audit.Q_MAKER_DELETE.put({'side': side, 'amount_remain': amount_remain})
                # 下单， 数量是删除订单时返回的
                if price < 0:
                    m = {'type': 'Delete and place new order',
                         'order_id': None,
                         'price': None,
                         'amount': None,
                         'amount_filled': None,
                         'name': name}
                    self.q_output.put(m)
                    continue
                this_amount = amount_remain or amount or amount_orig
                if this_amount < self.t_mkt.minimum_amount:
                    logger.info("Delete and place new order: amount %s is less than minimum required amount(%s), set amount to %s" % (amount, self.t_mkt.minimum_amount, amount_orig))
                    this_amount = amount_orig or amount
                if side == 'buy':
                    res = self.t_mkt.buy(amount=this_amount, price=price)
                else:
                    res = self.t_mkt.sell(amount=this_amount, price=price)
                Audit.Q_MAKER.put({"amount": this_amount, "side": side})
                if not res:
                    m = {'type': 'Delete and place new order',
                         'order_id': None,
                         'price': None,
                         'amount': None,
                         'amount_filled': None,
                         'name': name}
                    action = "maker_{}_fail".format(side)
                    Recorder.record(action, amount=this_amount, price=price, taker_platform=name)
                else:
                    # 乱序返回信息，有可能无法getOrder
                    if self.name == "Bitfinex":
                        order_details = res
                    else:
                        order_details = self.t_mkt.getOrder(res['order_id'])
                    m = {'type': 'Delete and place new order',
                         'order_id': order_details['order_id'],
                         'price': order_details['price'],
                         'amount': order_details['amount_orig'],
                         'amount_filled': order_details['amount_filled'],
                         'name': name}
                    action = "maker_{}".format(side)
                    Recorder.record(action, amount=this_amount, price=price, order_id=order_details['order_id'], taker_platform=name)
                self.q_output.put(m)

            elif m['type'] == 'Trade back':
                # {'type': 'Trade back', 'amount_to_trade_back': amount_to_trade_back, 'initial_amount': self.initial_amount, 'reference_price': reference_price}
                self.trade_back(amount_to_trade_back=m['amount_to_trade_back'],
                                initial_amount=m['initial_amount'],
                                reference_price=m['reference_price'])
                self.q_output.put({"status": True})

            elif m['type'] == 'Delete all orders':
                '''
                ret = {"buy":[], "sell":[]}
                '''
                orders_list = m['order_ids']
                for side, order_id_list in orders_list.items():
                    for order_id in order_id_list:
                        try:
                            result = self.t_mkt.deleteOrder(order_id)
                            amount_remain = result['amount_remain']
                            action = "maker_delete"
                            Recorder.record(action, amount=amount_remain, order_id=order_id, taker_platform=None)
                            if amount_remain:
                                Audit.Q_MAKER_DELETE.put({'side': side, 'amount_remain': amount_remain})
                            logger.info('Delete all orders %s' % order_id)
                        except Exception as ex:
                            logger.error("Delete all orders err: %s" % ex)
                self.q_output.put({"status": True})


class BitfinexTargetMarget(TargetMargetWs):
    def __init__(self, meta_code, strategy_id):
        super(BitfinexTargetMarget, self).__init__(BitfinexSpotWs, meta_code, strategy_id)

class BinanceTargetMarget(TargetMargetWs):
    def __init__(self, meta_code, strategy_id):
        super(BinanceTargetMarget, self).__init__(BinanceSpotWs, meta_code, strategy_id)

class HuobiTargetMarget(TargetMargetWs):
    def __init__(self, meta_code, strategy_id):
        super(HuobiTargetMarget, self).__init__(HuobiRest, meta_code, strategy_id)

    def mkt_buy(self, amount_to_be_filled, reference_price):
        res = self.t_mkt.buy(amount=amount_to_be_filled*reference_price)
        return res

    def mkt_sell(self, amount_to_be_filled, reference_price):
        res = self.t_mkt.sell(amount=amount_to_be_filled)
        return res

class OkexWsTargetMarget(TargetMargetWs):
    def __init__(self, meta_code, strategy_id):
        super(OkexWsTargetMarget, self).__init__(OkexSpotWs, meta_code, strategy_id)

    def mkt_buy(self, amount_to_be_filled, reference_price):
        res = self.t_mkt.buy(price=amount_to_be_filled*reference_price)
        return res


class NewMaker(object):
    def __init__(self, config_name="configMaker_ethbtc.json", target_market=None):

        self.task_on_do = 0
        self.c = 0
        self.error_c = {}
        self.allow_buy_and_sell={}

        # self.task_holder = threading.Event()
        # self.task_holder.set()
        self.config_name = config_name
        self.config = json.load(open(config_name,'r'))

        self.thres = self.config["thres"]
        self.min_thres = self.config["min_thres"]
        self.max_thres = self.config["max_thres"]


        self.initial_amount = self.config["initial_amount"]
        self.maxTradeRatio = self.config["maxTradeRatio"]
        # self.max_task_on_do = self.config["max_task_on_do"]
        self.target_mkt = target_market or self.config["target_market"]
        self.meta_code = self.config["meta_code"]
        self.strategy_id = self.config["strategy_id"]
        self.Binance_new_order_thres = self.config["Binance_new_order_thres"]
        self.holder = threading.Event()
        self.holder.set()

        if self.target_mkt == "Binance":
            # 促进币安成交改动的阈值
            r = 0.6
            DynamicThres.load_thres(thres=self.thres * r,
                                    min_thres=self.min_thres * r,
                                    max_thres=self.max_thres * r,
                                    initial_amount=self.initial_amount)
        else:
            DynamicThres.load_thres(thres=self.thres,
                                    min_thres=self.min_thres,
                                    max_thres=self.max_thres,
                                    initial_amount=self.initial_amount)

        self.mkt = collections.OrderedDict()
        self.generateTargetMkt(self.target_mkt)
        self.generateObjs()
        # 记录各交易所对应的order id
        self.active_orders = {}
        # 记录各交易所市价，部分交易所市价买需要通过价格换算
        self.mkt_price = {}
        # self.accumulative_amount = {}
        self.abandoned_task = []
        self.ab_lock = threading.Lock()
        self.hist = collections.OrderedDict()
        self.queue = self.mkt[self.target_mkt].q_order_result
        # self.okex_mkt_price = None
        for mkt in self.mkt:
            self.active_orders[mkt] = {'buy': None, 'sell': None}
            self.mkt_price[mkt] = {'buy': None, 'sell': None}
            # self.accumulative_amount[mkt] = {'buy': 0, 'sell': 0}
            self.error_c[mkt] = 0
            Profit.LOSS[mkt] = False

        self.market_monitor = MarketStatus(config_file, target_market, self.mkt)

        self.deliver = threading.Thread(target=self.task_deliver)
        self.deliver.setDaemon(True)
        self.deliver.start()

        time.sleep(15)

        self.initial_print_account()

    def hold(self):
        self.holder.clear()
        self.holder.wait()

    def thresCoin(self, list, thres=1.0):
        acc = 0
        for i in range(len(list)):
            acc += float(list[i]['amount'])  # amount
            if acc > thres:
                return float(list[i]['price'])  # price
        return float(list[-1]['price'])

    def updateHist(self, message):
        if message['buy']['ordid']:
            self.hist.update({message['buy']['ordid']: message['name']})
        if message['sell']['ordid']:
            self.hist.update({message['sell']['ordid']: message['name']})
        # 存100个最近的订单
        if len(self.hist) > 100:
            self.hist.popitem(last=False)

    def generateTargetMkt(self, type):
        meta_code = self.meta_code
        t_mkt = None
        if type == "Bitfinex":
            t_mkt = BitfinexTargetMarget(meta_code=meta_code, strategy_id=self.strategy_id)
        if type == "Binance":
            t_mkt = BinanceTargetMarget(meta_code=meta_code, strategy_id=self.strategy_id)
        if type == "HuoBiPro":
            t_mkt = HuobiTargetMarget(meta_code=meta_code, strategy_id=self.strategy_id)
        if type == "OKEX":
            t_mkt = OkexWsTargetMarget(meta_code=meta_code, strategy_id=self.strategy_id)
            # return OkexTaker(meta_code=meta_code)
        assert t_mkt is not None
        t_mkt.setDaemon(True)
        t_mkt.start()
        self.mkt[type] = t_mkt

    def generateObj(self, type, meta_code):
        if type == "Bitfinex":
            return BitfinexTaker(meta_code=meta_code, strategy_id=self.strategy_id, config_name=self.config_name)
        if type == "Binance":
            return BinanceTaker(meta_code=meta_code, strategy_id=self.strategy_id, config_name=self.config_name)
        if type == "HuoBiPro":
            return HuobiTaker(meta_code=meta_code, strategy_id=self.strategy_id, config_name=self.config_name)
        if type == "OKEX":
            return OkexWsTaker(meta_code=meta_code, strategy_id=self.strategy_id, config_name=self.config_name)
            # return OkexTaker(meta_code=meta_code)

    def generateObjs(self):
        for key, value in self.config["trade_obj"].items():
            trade = value['trade']
            if key == self.target_mkt or not trade:
                continue
            obj = self.generateObj(type=key, meta_code=self.meta_code)
            obj.setDaemon(True)
            obj.start()
            self.mkt[key] = obj

    def initial_print_account(self):
        account_data = {}
        for mkt, obj in self.mkt.items():
            if obj.available and obj.status and obj.latency_good:
                account = obj.getAccount()
                account_data[mkt] = account
        logger.info(account_data)

    def getAccount(self):
        self.currentPrice = {}
        self.currentAccount = collections.OrderedDict()
        for mkt, obj in self.mkt.items():
            if obj.available and obj.status and obj.latency_good and not Profit.LOSS[mkt]:
                account = obj.getAccount()
                self.currentAccount.update({mkt: account})
                price = obj.getDepth()
                self.currentPrice.update({mkt: price})
            # taker列队处于阻塞状态
            elif mkt != self.target_mkt and not obj.taker_holder.is_set():
                amount_to_trade_back = obj.calc_amount_in_queue()
                if amount_to_trade_back:
                    reference_price = (self.mkt_price[self.target_mkt]['buy'] + self.mkt_price[self.target_mkt][
                        'sell']) / 2
                    self.mkt[self.target_mkt].q.put(
                        {'type': 'Trade back',
                         'amount_to_trade_back': amount_to_trade_back,
                         'initial_amount': self.initial_amount,
                         'reference_price': reference_price})
                    self.mkt[self.target_mkt].q_output.get()

    def _get_active_orders(self):
        '''
        self.active_orders[mkt] = {'buy': None, 'sell': None}
        :return:
        '''
        ret = {"buy":[], "sell":[]}
        for mkt, active_orders in self.active_orders.items():
            for side, order_id in active_orders.items():
                if order_id:
                    ret[side].append(order_id)
        return ret

    def _cancel_all_active_orders(self):
        act_order_list = self._get_active_orders()
        if act_order_list["buy"] or act_order_list["sell"]:
            self.mkt[self.target_mkt].q.put({'type': 'Delete all orders', 'order_ids': act_order_list})
            self.mkt[self.target_mkt].q_output.get()
            for mkt in self.mkt:
                self.active_orders[mkt] = {'buy': None, 'sell': None}

    def checkAccount(self):
        # maker异常，直接跳过不进行下单操作
        if not (self.mkt[self.target_mkt].status and self.mkt[self.target_mkt].available and self.mkt[
            self.target_mkt].latency_good):
            logger.error("Maker is down")
            self._cancel_all_active_orders()
            return
        self.thres, self.min_thres, self.max_thres, self.initial_amount = DynamicThres.get_thres()
        self.depthValid = []
        for mkt, account in self.currentAccount.items():
            if not self.mkt[mkt].available or not self.mkt[mkt].status or not self.mkt[mkt].latency_good or Profit.LOSS[mkt]:
                continue
            while True:
                depth = None
                try:
                    depth = self.currentPrice[mkt]
                    # sell_price = depth['asks'][0]['price']
                    # buy_price = depth['bids'][0]['price']
                    sell_price = self.thresCoin(depth['asks'], self.initial_amount)
                    buy_price = self.thresCoin(depth['bids'], self.initial_amount)
                    break
                except Exception as ex:
                    logger.error('checkAccount(%s), Retry in 1 seconds: %s, %s' % (mkt, ex, depth))
                    time.sleep(1)
            self.mkt_price[mkt]['sell'] = sell_price
            self.mkt_price[mkt]['buy'] = buy_price
            model = {
                "name": mkt,
                "sell": sell_price,
                "buy": buy_price,
                "sell_o": True,
                "buy_o": True,
            }
            if self.currentAccount[mkt][self.mkt[mkt].base_coin] < self.maxTradeRatio * self.initial_amount*model['buy']:
                model["buy_o"] = False
            if self.currentAccount[mkt][self.mkt[mkt].target_coin] < self.maxTradeRatio * self.initial_amount:
                model["sell_o"] = False
            self.depthValid.append(model)

            self.check_abandoned_task()

            # 多平台
            if model['name'] == self.target_mkt or self.depthValid[0]['name'] != self.target_mkt:
                if self.depthValid[0]['name'] != self.target_mkt:
                    logger.error("depthValid %s" % self.depthValid)
                continue
            # target_market必须放在第一位
            # assert self.depthValid[0]['name'] == self.target_mkt
            # if not self.mkt[model['name']].status:
            #     continue
            # 对于每一个平台的差价都是目标差价+target_market的maker交易费率+当前mkt的taker交易费率
            this_thres = round(self.thres + self.mkt[self.target_mkt].fee_rate + self.mkt[model['name']].fee_rate_taker, 10)
            this_max_thres = round(self.max_thres + self.mkt[self.target_mkt].fee_rate + self.mkt[model['name']].fee_rate_taker, 10)
            this_min_thres = round(self.min_thres + self.mkt[self.target_mkt].fee_rate + self.mkt[model['name']].fee_rate_taker, 10)
            # print(model['name'], 'thres:', this_thres, this_max_thres, this_min_thres)
            buy_allowed = self.depthValid[0]['buy_o'] and model['sell_o']
            sell_allowed = self.depthValid[0]['sell_o'] and model['buy_o']
            # print(model['name'], buy_allowed, sell_allowed)
            self.mkt[self.target_mkt].q.put({'type': 'Get buy and sell orders', 'name': model['name'], 'order_id': self.active_orders[mkt]})
            m = self.mkt[self.target_mkt].q_output.get()
            assert m['name'] == model['name']
            # print('Get buy and sell orders', m)
            self.updateHist(m)
            my_bp = m['buy']['price']  # 如果有价格,则单子还未成交,如果是None,说明之前的单子已经成交
            my_sp = m['sell']['price']
            buy_amount_remain = m['buy']['amount_remain']
            sell_amount_remain = m['sell']['amount_remain']
            buy_amount_target = m['buy']['amount_remain'] if m['buy']['amount_remain'] else self.initial_amount
            sell_amount_target = m['sell']['amount_remain'] if m['sell']['amount_remain'] else self.initial_amount

            if buy_allowed:
                if not buy_amount_remain:  # 之前的买单已经成交, 下新买单
                    # target_buy_price = round(model['sell'] * (1 - this_thres), self.precise)
                    target_buy_price = model['buy'] * (1 - this_thres)
                    # 如果大于最低阈值，按maker买一价格挂单
                    # if model['buy'] * (1 - this_min_thres) > self.depthValid[0]['buy']:
                    #     target_buy_price = self.depthValid[0]['buy']
                    if self.target_mkt == "Binance" and target_buy_price < self.depthValid[0]['buy'] * (1 - self.Binance_new_order_thres):
                        logger.debug("Binance buy price diff: %s, %s" % (target_buy_price, self.depthValid[0]['buy'] * (1- self.Binance_new_order_thres)))
                    else:
                        self.mkt[self.target_mkt].q.put({'type': 'New order', 'price': target_buy_price, 'amount': self.initial_amount,'side': 'buy', 'name': model['name']})
                        message = self.mkt[self.target_mkt].q_output.get()
                        # print(message)
                        assert message['name'] == model['name']
                        order_id = message['order_id']
                        if order_id:
                            self.active_orders[mkt]['buy'] = order_id
                            self.hist[order_id] = mkt
                            logger.info('New order(to %s): %s Buy %s @%s' % (model['name'], message['order_id'], self.initial_amount, target_buy_price))

                # elif model['sell'] * (1 - this_min_thres) < my_bp or model['sell'] * (1 - this_max_thres) > my_bp:
                elif model['buy'] * (1 - this_min_thres) < my_bp or model['buy'] * (1 - this_max_thres) > my_bp:
                    if buy_amount_target < self.mkt[mkt].minimum_amount:
                        buy_amount_target += self.initial_amount
                    # target_buy_price = round(model['sell'] * (1 - this_thres), self.precise)
                    target_buy_price = model['buy'] * (1 - this_thres)
                    # if model['buy'] * (1 - this_min_thres) > self.depthValid[0]['buy']:
                    #     target_buy_price = self.depthValid[0]['buy']
                    if self.target_mkt == "Binance" and target_buy_price < self.depthValid[0]['buy'] * (1 - self.Binance_new_order_thres):
                        logger.debug("Binance buy price diff: %s, %s" % (target_buy_price, self.depthValid[0]['buy'] * (1- self.Binance_new_order_thres)))
                        target_buy_price = -1
                    self.mkt[self.target_mkt].q.put({'type': 'Delete and place new order', 'side': 'buy', 'price': target_buy_price,'amount': buy_amount_target, 'name': model['name'], 'order_id': self.active_orders[mkt]})
                    message = self.mkt[self.target_mkt].q_output.get()
                    # print(message)
                    assert message['name'] == model['name']
                    order_id = message['order_id']
                    if order_id:
                        self.active_orders[mkt]['buy'] = order_id
                        self.hist[order_id] = mkt
                        logger.info('Delete and place new order(to %s): Buy %s @%s, past: @%s' % (model['name'], buy_amount_target, target_buy_price, my_bp))
                    else:
                        self.active_orders[mkt]['buy'] = order_id

            if sell_allowed:
                if not sell_amount_remain:
                    # target_sell_price = round(model['buy'] / (1 - this_thres),self.precise)
                    target_sell_price = model['sell'] / (1 - this_thres)
                    # if model['sell'] / (1 - this_min_thres) < self.depthValid[0]['sell']:
                    #     target_sell_price = self.depthValid[0]['sell']
                    if self.target_mkt == "Binance" and target_sell_price > self.depthValid[0]['sell']/(1-self.Binance_new_order_thres):
                        logger.debug("Binance sell price diff: %s, %s" % (target_sell_price, self.depthValid[0]['sell']*(1+self.Binance_new_order_thres)))
                    else:
                        self.mkt[self.target_mkt].q.put({'type': 'New order', 'price':target_sell_price, 'amount': self.initial_amount,'side': 'sell', 'name': model['name']})
                        message = self.mkt[self.target_mkt].q_output.get()
                        # print(message)
                        assert message['name'] == model['name']
                        order_id = message['order_id']
                        if order_id:
                            self.active_orders[mkt]['sell'] = order_id
                            self.hist[order_id] = mkt
                            logger.info('New order(to %s): %s Sell %s @%s' % (model['name'], message['order_id'], self.initial_amount, target_sell_price))

                # elif model['buy'] / (1 - this_min_thres) > my_sp or model['buy'] / (1 - this_max_thres) < my_sp:
                elif model['sell'] / (1 - this_min_thres) > my_sp or model['sell'] / (1 - this_max_thres) < my_sp:
                    if buy_amount_target < self.mkt[mkt].minimum_amount:
                        buy_amount_target += self.initial_amount
                    # target_sell_price = round(model['buy'] / (1 - this_thres),self.precise)
                    target_sell_price = model['sell'] / (1 - this_thres)
                    # if model['sell'] / (1 - this_min_thres) < self.depthValid[0]['sell']:
                    #     target_sell_price = self.depthValid[0]['sell']
                    if self.target_mkt == "Binance" and target_sell_price > self.depthValid[0]['sell']/(1-self.Binance_new_order_thres):
                        logger.debug("Binance sell price diff: %s, %s" % (target_sell_price, self.depthValid[0]['sell']*(1+self.Binance_new_order_thres)))
                        target_sell_price = -1
                    self.mkt[self.target_mkt].q.put({'type': 'Delete and place new order', 'side': 'sell', 'price': target_sell_price,'amount': sell_amount_target, 'name': model['name'], 'order_id': self.active_orders[mkt]})
                    message = self.mkt[self.target_mkt].q_output.get()
                    # print(message)
                    assert message['name'] == model['name']
                    order_id = message['order_id']
                    if order_id:
                        self.active_orders[mkt]['sell'] = order_id
                        self.hist[order_id] = mkt
                        logger.info('Delete and place new order(to %s): Sell %s @%s, past: @%s' % (model['name'], sell_amount_target, target_sell_price, my_sp))
                    else:
                        self.active_orders[mkt]['sell'] = order_id

    def could_be_shut_down(self):
        flag = True

        self._cancel_all_active_orders()

        while True:
            for key, obj in self.mkt.items():
                if key == self.target_mkt:
                    continue
                if obj.q.qsize() == 0 or obj.error_c >= 5:
                    taker_task_done = True
                else:
                    taker_task_done = False
                logger.info("Taker %s Shutting down: %s tasks and %s errors" % (key, obj.q.qsize(), obj.error_c))
                flag = flag and taker_task_done
            if flag:
                logger.info("Takers Shutting down in 5s.")
                time.sleep(5)
                return flag
            else:
                time.sleep(1)
                continue

    def check_abandoned_task(self):
        d = copy(self.abandoned_task)
        task_id = []
        for m in d:
            if m['order_id'] in self.hist:
                self.queue.put(m)
                task_id.append(m)
        for m in task_id:
            with self.ab_lock:
                self.abandoned_task.remove(m)

    def task_deliver(self):
        time.sleep(5)
        while True:
            try:
                m = self.queue.get()
                order_id = m.get('order_id')
                logger.debug("Main Thread get m: %s" % m)
                # print(m, self.hist, self.active_orders)
                if order_id in self.hist:
                # for mkt, orders in self.active_orders.items():
                    # if orders['buy'] == order_id or orders['sell'] == order_id:
                    amount_to_be_filled = 0
                    if m['amount_filled_this_time']:
                        amount_to_be_filled = m['amount_filled_this_time']
                    elif m['amount_filled']:
                        amount_to_be_filled = m['amount_filled']
                    if amount_to_be_filled > 0:
                        taker_market = self.hist[order_id]
                        fee_rate = {"maker_fee": self.mkt[self.target_mkt].fee_rate,
                                    "taker_fee": self.mkt[taker_market].fee_rate_taker}
                        m.update(fee_rate)
                        reference_price = (self.mkt_price[taker_market]['buy'] + self.mkt_price[taker_market]['sell']) / 2
                        m['amount_to_be_filled'] = amount_to_be_filled
                        m['reference_price'] = reference_price
                        # 补单
                        DynamicThres.deal()
                        self.mkt[taker_market].q.put(m)
                        # try:
                        #     if not m['amount_remain']:
                                # del self.active_orders[self.hist[order_id]][m.get('side')]
                        #         del self.hist[order_id]
                        # except:
                        #     pass
                        # print('task delivered:', m)
                else:
                    with self.ab_lock:
                        logger.debug("abandoned_task add: %s" % m)
                        self.abandoned_task.append(m)
            except Exception as ex:
                logger.error("task_deliver: %s" % ex)
            # if not self.check_task_on_do() and not self.task_holder.is_set():
            #     self.task_holder.set()

def get_t_mkt():
    config_map = {'1':'Bitfinex', '2':'Binance', '3':'HuoBiPro', '4':'OKEX'}
    global sleep_interval

    if len(sys.argv) == 2:
        print('Set Target Market to: %s' % config_map[sys.argv[1]])
        logger = logging.getLogger("dquant")
        fh = logging.FileHandler('../../logs/app-%s.log' % (config_map[sys.argv[1]]), mode='w')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        if sys.argv[1] == '2':
            sleep_interval = 1
        return config_map[sys.argv[1]], 'configMaker_ethbtc.json'

    elif len(sys.argv) == 3:
        # pass
        # 1:json_file; 2:market
        logger = logging.getLogger("dquant")
        fh = logging.FileHandler('../../logs/app-%s-%s.log' % (sys.argv[1], config_map[sys.argv[2]]), mode='w')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        logger.info('Set config file to: %s, Market to: %s' % (sys.argv[1], config_map[sys.argv[2]]))
        if sys.argv[2] == '2':
            sleep_interval = 1
        return config_map[sys.argv[2]], sys.argv[1]

    else:
        logger = logging.getLogger("dquant")
        fh = logging.FileHandler('../../logs/app-default.log', mode='w')
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        return None, 'configMaker_ethbtc.json'


class TickerHeartbeats(object):
    def __init__(self, target_market):
        self.q_hb = queue.Queue()
        self.target_market = target_market

    def hb(self):
        self.q_hb.put({'hb': int(time.time()), 'name': self.target_market})


class GracefulKiller():
    kill_now = False
    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self,signum, frame):
        self.kill_now = True



if __name__ == '__main__':
    os.environ[Constants.DQUANT_ENV] = "dev"
    target_market, config_file = get_t_mkt()
    ticker_hb = TickerHeartbeats(target_market)
    auditor = Audit(config_file)
    d_thres = DynamicThres(target_market, config_file)
    killer = GracefulKiller()
    global sleep_interval
    sleep_interval = 0.4
    new_maker = NewMaker(target_market=target_market, config_name=config_file)
    t = time.time()
    tick = 0
    logger.debug('sleep_interval: %s' % sleep_interval)

    doctor = BlockAlarm(ticker_hb.q_hb)
    doctor.setDaemon(True)
    doctor.start()
    recorder = Recorder(target_market, config_file)
    recorder.setDaemon(True)
    recorder.start()

    profit = Profit(target_market=target_market, config_name=config_file)
    profit.setDaemon(True)
    profit.start()

    while True:
        t1 = time.time()
        m, s = divmod(t1 - t, 60)
        h, m = divmod(m, 60)
        logger.info("tick %d %02d:%02d:%02d" % (tick, h, m, s))
        Recorder.update_tick(tick)
        ticker_hb.hb()
        d_thres.start_timer()
        # auditor.check()
        if auditor.need_to_hold():
            new_maker._cancel_all_active_orders()
            new_maker.hold()
        new_maker.getAccount()
        new_maker.checkAccount()
        tick += 1
        # API访问限制，设置延时
        time.sleep(sleep_interval)
        if killer.kill_now and new_maker.could_be_shut_down():
            break
    logger.info("End of the program. Maker was killed gracefully :)")
    try:
        sys.exit(0)
    except Exception as ex:
        logger.error("Exit: %s" % ex)