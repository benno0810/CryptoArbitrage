import json
import logging
import os
import queue
import threading
import asyncio
import collections
import time

from copy import copy

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
rootPath = os.path.split(rootPath)[0]
os.sys.path.append(rootPath)

from dquant.common.alarms import BlockAlarm
from dquant.constants import Constants
from dquant.strategy.Bitfinex2Binance import TickerHeartbeats
from dquant.markets._binance_spot_ws import BinanceSpotWs
from dquant.markets._bitfinex_spot_ws import BitfinexSpotWs
from dquant.markets._huobi_spot_rest import HuobiRest
from dquant.markets._okex_spot_ws_v2 import OkexSpotWs

logger = logging.getLogger("dquant")
logger.setLevel(logging.DEBUG)
# ch = logging.StreamHandler()
# ch.setLevel(logging.INFO)
fh = logging.FileHandler('../../logs/SpotDiff.log', mode='w')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
# ch.setFormatter(formatter)
logger.addHandler(fh)
# logger.addHandler(ch)

config_name = "configSpotDiff.json"



class Audit(object):
    Q_MAKER = queue.Queue()
    Q_MAKER_DELETE = queue.Queue()
    Q_AMOUNT_FILLED = queue.Queue()
    def __init__(self, config_name):
        self.maker_buy_balance = 0.0
        self.maker_sell_balance = 0.0
        self.config = json.load(open(config_name, 'r'))
        self.dangerous_balance = self.config["dangerous_balance"]
        self.audit_reset_interval = self.config["audit_reset_interval"]

        self.lock = threading.Lock()
        self.holder = threading.Event()
        self.reset_audit_event = threading.Event()

        get_maker_amount_thread = threading.Thread(target=self.get_maker_amount)
        get_maker_amount_thread.setDaemon(True)
        get_maker_amount_thread.start()

        get_maker_delete_thread = threading.Thread(target=self.get_maker_delete)
        get_maker_delete_thread.setDaemon(True)
        get_maker_delete_thread.start()

        get_amount_filled_thread = threading.Thread(target=self.get_amount_filled)
        get_amount_filled_thread.setDaemon(True)
        get_amount_filled_thread.start()

        self.reset_audit_thread(self.reset_audit_event, self.audit_reset_interval)

    def get_maker_amount(self):
        while True:
            try:
                # {side:"buy", amount:0.4}
                # 监控成交结果，而不是下单动作
                m_maker = Audit.Q_MAKER.get()
                logger.debug("m_maker: %s" % m_maker)
                with self.lock:
                    if m_maker["side"] == "buy":
                        self.maker_buy_balance += float(m_maker["amount"])
                    elif m_maker["side"] == "sell":
                        self.maker_sell_balance += float(m_maker["amount"])
            except Exception as ex:
                logger.error("get_maker_amount: %s" % ex)


    def get_amount_filled(self):
        while True:
            try:
                m_amount_filled = Audit.Q_AMOUNT_FILLED.get()
                logger.debug("m_taker: %s" % m_amount_filled)
                with self.lock:
                    complex_side = m_amount_filled['side'].lower()
                    simple_side = 'buy' if complex_side.startswith('buy') else 'sell'
                    amount_filled = m_amount_filled['amount_filled_this_time'] or m_amount_filled['amount_filled']
                    if simple_side == "buy":
                        self.maker_buy_balance -= float(amount_filled)
                    elif simple_side == "sell":
                        self.maker_sell_balance -= float(amount_filled)
            except Exception as ex:
                logger.error("get_amount_filled: %s" % ex)


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
            self.maker_buy_balance = 0
            self.maker_sell_balance = 0

    def check(self):
        logger.debug('maker balance: %s, %s' % (self.maker_buy_balance, self.maker_sell_balance))
        if abs(self.maker_buy_balance) >= self.dangerous_balance or \
                abs(self.maker_sell_balance) >= self.dangerous_balance or \
                abs(self.maker_buy_balance - self.maker_sell_balance) >= self.dangerous_balance:
            logger.error("Audit: Hold on!")
            self.holder.clear()
            self.holder.wait()


class TargetMargetWs(threading.Thread):
    def __init__(self, mkt, meta_code, strategy_id, config_name=config_name):
        super(TargetMargetWs, self).__init__()
        self.config = json.load(open(config_name, 'r'))
        self.new = asyncio.new_event_loop()
        asyncio.set_event_loop(self.new)
        self.t_mkt = mkt(meta_code, self.new)
        self.t_mkt.strategy_id = strategy_id
        self.minimum_amount = self.t_mkt.minimum_amount
        self.target_coin = self.t_mkt.market_currency
        self.name = self.t_mkt.name
        self.base_coin = self.t_mkt.base_currency
        self.fee_rate = self.t_mkt.fee_rate
        # self.minimun_amount = self.t_mkt.minimum_amount
        # 不需要监控订单成交情况，只要在取消的时候返回剩余就可以了
        # 2018/6/26 更新: 需要监控订单成交情况，风控
        self.t_mkt.order_result_required = True
        self.t_mkt.start()
        self.q_order_result = self.t_mkt.q_order_result
        self.q = queue.Queue()
        self.q_output = queue.Queue()
        # 仓位
        self.lastPosition = {}
        self.accumulative_amount = {'buy': 0, 'sell': 0}
        self.error_c = 0
        self.new_order_error_c = 0
        self.c = 0
        self.available = True
        self.status = True
        self.latency_good = self.t_mkt.latency_good
        self.last_get_order_info = {'buy': {'ordid': None, 'amount_filled': None},
                                    'sell': {'ordid': None, 'amount_filled': None}}
        self.taker_holder = threading.Event()
        self.check_alive_times = 0
        self.wake_interval = self.config["taker_wake_interval"]
        self.wallet_lock = threading.Lock()
        self.wallet = {}

        get_account_thread = threading.Thread(target=self.getAccountThread)
        get_account_thread.setDaemon(True)
        get_account_thread.start()

        collect_amount_filled_thread = threading.Thread(target=self.collect_amount_filled)
        collect_amount_filled_thread.setDaemon(True)
        collect_amount_filled_thread.start()

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
            time.sleep(10)
            self.available = True

    def check_alive_thread(self, interval):
        timerThread = threading.Timer(interval=interval, function=self.check_alive)
        timerThread.start()

    def mkt_buy(self, amount_to_be_filled, reference_price):
        '''
        :param amount_to_be_filled: amount that need to be filled
        :param reference_price: for some exchanges(OKEX), market-buy require the arg 'price' therefore amount needs to be converted to price
        :return:
        '''
        return self.t_mkt.buy(amount=amount_to_be_filled)

    def mkt_sell(self, amount_to_be_filled):
        return self.t_mkt.sell(amount=amount_to_be_filled)

    def getDepth(self):
        try:
            depth = self.t_mkt.getDepth()
            return depth
        except TimeoutError as ex:
            self.available = False
            try:
                t = ex.args
                seconds = t[0] if (t and t[0]) else self.wake_interval
                logger.info("Market %s will be wake up %s seconds later" % (self.name, seconds))
                self.check_alive_thread(seconds)
            except Exception as ex:
                logger.error("Market %s getAccount: %s" % (self.name, ex))
            finally:
                return None

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
            account = self.t_mkt.getAccount(coin=coin)
        except TimeoutError as ex:
            self.available = False
            try:
                t = ex.args
                seconds = t[0] if (t and t[0]) else self.wake_interval
                logger.info("Market %s will be wake up %s seconds later" % (self.name, seconds))
                self.check_alive_thread(seconds)
            except Exception as ex:
                logger.error("Market %s getAccount: %s" % (self.name, ex))
            finally:
                return None

        if 'exchange' in account:
            return account['exchange']
        return account

    def collect_amount_filled(self):
        while True:
            try:
                order_result = self.q_order_result.get()
                Audit.Q_AMOUNT_FILLED.put(order_result)
            except Exception as ex:
                logger.error("%s collect_amount_filled: %s" % (self.name, ex))

    # 返回最后一个买/卖/删除记录，因为getorder不会记录已经成交或者删除的订单信息,而已经执行的订单保存在bfx.getHist里（只保存最近10个）
    def get_latest_order(self, side=None, order_id=None):
        # 查询买卖订单
        if side and order_id:
            hist = self.t_mkt.getHist(side=side, order_id=order_id)
            return hist
        else:
            return {'status': False}

    def run(self):
        while True:
            m = self.q.get()
            # print(m)
            if m['type'] == 'New order':
                '''
                {'type': 'New order',
                         'price': buy_price,
                         'amount': self.initial_amount,
                         'side': 'buy',
                         'name': buy_mkt})
                '''
                price = m['price']
                side = m['side']
                amount = m['amount']
                name = m['name']
                if side == 'buy':
                    result = self.t_mkt.buy(amount=amount, price=price)
                else:
                    result = self.t_mkt.sell(amount=amount, price=price)
                Audit.Q_MAKER.put({"amount": amount, "side": side})
                order_id = None
                if not result:
                    m = {'type': 'New order',
                         'order_id': None,
                         'amount': None,
                         'name': name}
                    logger.error('%s t_mkt buy: %s' % (name, result))
                    self.new_order_error_c += 1

                # print(result)
                elif 'order_id' in result:
                    order_details = self.t_mkt.getOrder(result['order_id'])
                    if order_details['status']:
                        order_id = order_details['order_id']
                        amount = order_details['amount_orig']
                        m = {'type': 'Order new',
                             'order_id': order_id,
                             'amount': amount,
                             'name': name}
                    else:
                        order_id= result['order_id']
                        amount = result.get('amount_orig', amount)
                        m = {'type': 'Order new',
                             'order_id': order_id,
                             'amount': amount,
                             'name': name}
                    self.lastPosition[order_id] = amount
                self.q_output.put(m)
                if m['order_id']:
                    self.new_order_error_c = 0
                    logger.info('New order (%s): %s %s %s @%s' % (name, order_id, side, amount, price))

            elif m['type'] == 'Delete order':
                '''
                {'type': 'Delete order',
                 'order_id': order_id,
                 'name': name}
                '''
                order_id = m['order_id']
                name = m['name']
                side = m['side']
                result = self.t_mkt.deleteOrder(order_id)
                # print(result)
                amount_remain = result['amount_remain']
                # 删除订单中有未成交的amount_remain,输出未成交的数量到屏幕
                if result['status']:
                    amount_filled = result['amount_filled']
                    # side = result['side']
                    logger.info('Delete: canceling order %s, filled %s, last position: %s' % (
                        order_id, amount_filled, self.lastPosition[order_id]))
                    if amount_remain:
                        self.lastPosition[order_id] = amount_remain
                    else:
                        del self.lastPosition[order_id]
                # 删除过程中成交了
                else:
                    try:
                        last_executed_order = self.get_latest_order(side=side, order_id=order_id)
                        amount_remain = last_executed_order['amount_remain']  # 正常情况下是0
                        amount_filled = last_executed_order['amount_filled']
                        # side = last_executed_order['side']
                        if not amount_remain:
                            amount_remain = 0
                        logger.info('Delete: id %s has been filled before deleted, amount: %s ' % (
                        last_executed_order['order_id'], amount_filled))
                        logger.info(
                            'Delete: canceling order %s, remaining %s' % (order_id, amount_remain))
                        if amount_remain:
                            self.lastPosition[order_id] = amount_remain
                        else:
                            del self.lastPosition[order_id]
                    except Exception as ex:
                        amount_remain = 0
                        logger.error(ex)

                if amount_remain:
                    Audit.Q_MAKER_DELETE.put({'side': side, 'amount_remain': amount_remain})

                # {'order_id':1, 'amount_remain':0.1, 'side':'buy'}
                self.q_output.put({'type': 'Delete order',
                                   'order_id': order_id,
                                   'amount_remain': amount_remain,
                                   'name': name,
                                   'side': side
                                   })

            elif m['type'] == 'Taker order':
                '''
                {'type': 'Taker order',
                 'price': self.best_price[side][0],
                 'amount': abs(amount_diff),
                 'side': side,
                 'name': taker_mkt}

                :return: {"type":Taker order, 'amount':0.1, 'name':'Bitfinex', 'side':'buy'}
                '''
                side = m.get('side')
                amount_to_be_filled = m['amount'] + self.accumulative_amount[side]
                reference_price = m.get('price', None)
                if amount_to_be_filled >= self.minimum_amount:
                    logger.info('Taker(%s) get task: %s, real amount: %s' % (self.name, m, amount_to_be_filled))
                    self.c += 1
                    try:
                        result = None
                        # 补单
                        if side == 'buy':
                            result = self.mkt_buy(amount_to_be_filled=amount_to_be_filled, reference_price=reference_price)
                        if side == 'sell':
                            result = self.mkt_sell(amount_to_be_filled=amount_to_be_filled)
                        # self.mkt[self.hist[order_id]].q.put(m)
                        if not result or ('status' in result and not result['status']):
                            logger.error("Taker error: %s failed to buy/sell (%s), Retry" % (self.name, m))
                            self.error_c += 1
                            self.q.put(m)
                        else:
                            logger.info('Taker(%s) task done: %s' % (self.name, result))
                            Audit.Q_MAKER.put({"amount": amount_to_be_filled, "side": side})
                            # self.error_c = 0
                            self.accumulative_amount[side] = 0
                    except Exception as ex:
                        logger.error("Taker error: %s (order details %s, info: %s)" % (self.name, m, ex))
                        self.error_c += 1
                        self.q.put(m)
                    finally:
                        self.c -= 1
                        # 某个Taker报错超过5次
                        if self.error_c >= 5:
                            logger.critical("Fatal Error: Taker %s seems not working properly, exit" % self.name)
                            self.status = False
                            self.taker_holder.clear()
                            self.taker_holder.wait()
                # 待交易量不满足交易所最小交易额度
                else:
                    self.accumulative_amount[side] += m['amount']
            if self.new_order_error_c >= 5:
                self.available = False
                logger.info("Market %s will be wake up %s seconds later" % (self.name, self.wake_interval))
                self.check_alive_thread(self.wake_interval)



class BitfinexTargetMarget(TargetMargetWs):
    def __init__(self, meta_code, strategy_id):
        super(BitfinexTargetMarget, self).__init__(BitfinexSpotWs, meta_code, strategy_id)


class BinanceTargetMarget(TargetMargetWs):
    def __init__(self, meta_code, strategy_id):
        super(BinanceTargetMarget, self).__init__(BinanceSpotWs, meta_code, strategy_id)

    def mkt_buy(self, amount_to_be_filled, reference_price):
        '''
        :param amount_to_be_filled: amount that need to be filled
        :param reference_price: for some exchanges(OKEX), market-buy require the arg 'price' therefore amount needs to be converted to price
        :return:
        '''
        res = self.t_mkt.buy(amount=amount_to_be_filled)
        return res

    def mkt_sell(self, amount_to_be_filled):
        res = self.t_mkt.sell(amount=amount_to_be_filled)
        return res


class HuobiTargetMarget(TargetMargetWs):
    def __init__(self, meta_code, strategy_id):
        super(HuobiTargetMarget, self).__init__(HuobiRest, meta_code, strategy_id)

    def mkt_buy(self, amount_to_be_filled, reference_price):
        return self.t_mkt.buy(amount=amount_to_be_filled*reference_price)

    def mkt_sell(self, amount_to_be_filled):
        return self.t_mkt.sell(amount=amount_to_be_filled)


class OkexWsTargetMarget(TargetMargetWs):
    def __init__(self, meta_code, strategy_id):
        super(OkexWsTargetMarget, self).__init__(OkexSpotWs, meta_code, strategy_id)

    def mkt_buy(self, amount_to_be_filled, reference_price):
        return self.t_mkt.buy(price=round(amount_to_be_filled*reference_price, 7))


class NewMaker(object):
    def __init__(self, config_name=config_name):

        self.allow_buy_and_sell = {}

        self.config = json.load(open(config_name, 'r'))

        self.diff_thres = self.config["diff_thres"]
        logger.info("diff_thres is: %s" % self.diff_thres)
        self.initial_amount = self.config["initial_amount"]
        self.maxTradeRatio = self.config["maxTradeRatio"]
        self.meta_code = self.config["meta_code"]
        # self.slippage = self.config["slippage"]

        self.strategy_id = self.config["strategy_id"]

        self.mkt = collections.OrderedDict()
        self.generateObjs()
        self.slippages = {}
        for mkt in self.mkt:
            self.slippages[mkt] = self.config["trade_obj"][mkt]["slippage"]
        # 记录各交易所对应的order id
        self.active_orders = {}
        # 记录各交易所市价，部分交易所市价买需要通过价格换算
        self.mkt_price = {}
        self.best_price = {}
        self.minimum_amount = {}
        self.hist = collections.OrderedDict()
        self.depthValid = []

        time.sleep(15)

        self.initial_print_account()

    def generateObj(self, type, meta_code):
        if type == "Bitfinex":
            return BitfinexTargetMarget(meta_code=meta_code, strategy_id=self.strategy_id)
        if type == "Binance":
            return BinanceTargetMarget(meta_code=meta_code, strategy_id=self.strategy_id)
        if type == "HuoBiPro":
            return HuobiTargetMarget(meta_code=meta_code, strategy_id=self.strategy_id)
        if type == "OKEX":
            return OkexWsTargetMarget(meta_code=meta_code, strategy_id=self.strategy_id)

    def generateObjs(self):
        for key, value in self.config["trade_obj"].items():
            trade_enabled = value['trade']
            if not trade_enabled:
                continue
            obj = self.generateObj(type=key, meta_code=self.meta_code)
            obj.setDaemon(True)
            obj.start()
            self.mkt[key] = obj

    def initial_print_account(self):
        account_data = {}
        for mkt, obj in self.mkt.items():
            account = obj.getAccount()
            account_data[mkt] = account
        logger.info(account_data)

        mkt_length = len(self.mkt)
        assert mkt_length >= 2
        mkt_list = list(self.mkt.keys())
        # init = {None: None}
        for i in range(mkt_length - 1):
            for j in range(i + 1, mkt_length):
                pair = "{}_{}".format(mkt_list[i], mkt_list[j])
                self.active_orders[pair] = {'buy': {None: None}, 'sell': {None: None}}
        # print('self.active_orders', self.active_orders)

    def getBestPrice(self):
        # 找出可交易市场中最低卖一价和最高买一价
        price_log = {}
        for model in self.depthValid:
            if not (self.mkt[model["name"]].available and self.mkt[model["name"]].status and self.mkt[model["name"]].latency_good):
                continue
            depth = self.mkt[model["name"]].getDepth()
            this_sell_1 = depth['asks'][0]['price']
            this_buy_1 = depth['bids'][0]['price']
            if model["buy_o"]:
                # 最合适市价买：没有最合适的买价，或者当前卖一价低于已存买价。taker将以市场最低卖一价买入。
                if not self.best_price['buy'][0] or this_sell_1 < self.best_price['buy'][0]:
                    self.best_price['buy'] = [this_sell_1, model["name"]]
            if model["sell_o"]:
                # 没有最合适的卖价，或者当前买一价低于已有卖价。taker将以市场最高买一价卖出。
                if not self.best_price['sell'][0] or this_buy_1 > self.best_price['sell'][0]:
                    self.best_price['sell'] = [this_buy_1, model["name"]]
            price_log[model["name"]] = {this_sell_1: model["buy_o"], this_buy_1: model["sell_o"]}
        logger.debug("getBestPrice: %s, price_log: %s." % (self.best_price, price_log))

    def getAccount(self):
        self.currentPrice = {}
        self.depthValid = []
        self.currentAccount = collections.OrderedDict()
        self.best_price = {'buy': [None, None], 'sell': [None, None]}
        for mkt, obj in self.mkt.items():
            if obj.available and obj.status and obj.latency_good:
                account = obj.getAccount()
                self.currentAccount.update({mkt: account})
                price = obj.getDepth()
                self.currentPrice.update({mkt: price})

        for mkt, account in self.currentAccount.items():
            if not self.mkt[mkt].available or not self.mkt[mkt].status or not self.mkt[mkt].latency_good:
                continue
            depth = self.currentPrice[mkt]
            sell_price = depth['asks'][0]['price']
            buy_price = depth['bids'][0]['price']

            model = {
                "name": mkt,
                "sell": sell_price,
                "buy": buy_price,
                "sell_o": True,
                "buy_o": True,
            }
            if self.currentAccount[mkt][self.mkt[mkt].base_coin] < self.maxTradeRatio * self.initial_amount * model[
                'buy']:
                model["buy_o"] = False
            if self.currentAccount[mkt][self.mkt[mkt].target_coin] < self.maxTradeRatio * self.initial_amount:
                model["sell_o"] = False
            self.depthValid.append(model)
            # 注意四个交易所都false的情况
            # if model["buy_o"]:
            #     # 没有最合适的买价，或者当前卖一价低于已有买价。taker将以市场最低卖一价买入。
            #     if not self.best_price['buy'][0] or model["sell"] < self.best_price['buy'][0]:
            #         self.best_price['buy'] = [model["sell"], model["name"]]
            # if model["sell_o"]:
            #     # 没有最合适的卖价，或者当前买一价低于已有卖价。taker将以市场最高买一价卖出。
            #     if not self.best_price['sell'][0] or model["buy"] > self.best_price['sell'][0]:
            #         self.best_price['sell'] = [model["buy"], model["name"]]
        # print('self.best_price', self.best_price)

    def cancelActiveOrdersAndTake(self):
        order_and_mkt = {}
        amount_diff = 0
        for pair in self.active_orders:
            # {order_id:[mkt, side]}
            for k, v in self.active_orders[pair]['buy'].items():
                order_and_mkt.update({k: [v, 'buy']})
            for k, v in self.active_orders[pair]['sell'].items():
                order_and_mkt.update({k: [v, 'sell']})
        # print('order_and_mkt', order_and_mkt)
        for order_id, mkt_side in order_and_mkt.items():
            if order_id and self.mkt[mkt_side[0]].available and self.mkt[mkt_side[0]].status and self.mkt[mkt_side[0]].latency_good:
                self.mkt[mkt_side[0]].q.put(
                    {'type': 'Delete order',
                     'order_id': order_id,
                     'name': mkt_side[0],
                     'side': mkt_side[1]
                     })
        for order_id, mkt_side in order_and_mkt.items():
            if order_id and self.mkt[mkt_side[0]].available and self.mkt[mkt_side[0]].status and self.mkt[mkt_side[0]].latency_good:
                # {'order_id':1, 'amount_remain':0.1, 'side':'buy'}
                m = self.mkt[mkt_side[0]].q_output.get()
                # print('Maker delete order receive', m)
                order_id = m['order_id']
                side = mkt_side[1]
                if m['order_id']:
                    for pair in self.active_orders:
                        if order_id in self.active_orders[pair][side]:
                            self.active_orders[pair][side] = {None: None}
                amount_remain = 0
                if side is 'buy':
                    amount_remain = m['amount_remain']
                if side is 'sell':
                    amount_remain = - m['amount_remain']
                amount_diff += amount_remain
        if not amount_diff:
            logger.info('Buy amount equals to sell amount')
            return
        taker_side = ''
        # 买入未成交的多，补买
        if amount_diff > 0:
            taker_side = 'buy'
        # 卖出未成交的多，补卖
        if amount_diff < 0:
            taker_side = 'sell'
        # 需要放入列队
        # 更新一下最合适价格
        self.getBestPrice()

        # 如果没有合适的taker，返回None，进入下一轮ticker
        if not (self.best_price['buy'][0] and self.best_price['sell'][0]):
            logger.info('Taker not available, %s' % self.depthValid)
            return None
        # 最合适的买价（taker 卖一价格） 高于最合适的卖价（taker买一价格）
        if self.best_price['buy'][0] >= self.best_price['sell'][0]:
            # logger.warning("Best buy price(%s) >= best sell price(%s)!, please check exchange and balance" % (self.best_price['buy'][0], self.best_price['sell'][0]))
            logger.info("Best buy price higher than sell price: %s" % self.depthValid)
            # return None

        taker_mkt = self.best_price[taker_side][1]
        # best price 已经判断过taker是否可用
        if taker_mkt:
            self.mkt[taker_mkt].q.put({'type': 'Taker order',
                                   'price': self.best_price[taker_side][0],
                                   'amount': abs(amount_diff),
                                   'side': taker_side,
                                   'name': taker_mkt})
            # {"type":Taker order, 'amount':0.1, 'name':'Bitfinex', 'side':'buy'}
            # m_taker = self.mkt[taker_mkt].q_output.get()
            # logger.info("Taker %s: %s %s" % (m_taker['name'], m_taker['side'].upper(), m_taker['amount']))
        else:
            logger.error('No available %s taker' % taker_side)

    def placeOrders(self):

        depthValid_length = len(self.depthValid)
        assert depthValid_length >= 2
        for i in range(depthValid_length - 1):
            for j in range(i + 1, depthValid_length):
                mkt1 = self.depthValid[i]
                mkt2 = self.depthValid[j]
                # 确认两个交易所可用
                if not (self.mkt[mkt1["name"]].status and self.mkt[mkt2["name"]].status and
                        self.mkt[mkt1["name"]].available and self.mkt[mkt2["name"]].available and
                        self.mkt[mkt1["name"]].latency_good and self.mkt[mkt2["name"]].latency_good):
                    continue
                sell_mkt = None
                sell_price = None
                buy_mkt = None
                buy_price = None
                # 双边都是作为maker挂单
                this_thres = round(self.diff_thres + self.mkt[mkt1["name"]].fee_rate + self.mkt[mkt2["name"]].fee_rate, 10)
                logger.debug("%s-%s this_thres: %s" % (mkt1["name"], mkt2["name"], this_thres))
                # print(mkt1["name"], mkt2["name"], this_thres)
                if mkt1["sell"]/mkt2["buy"] > max(1+this_thres, mkt2["sell"]/mkt1["buy"]) and (
                    mkt1["sell_o"] and mkt2["buy_o"]):
                    logger.info('satisfied price different between %s and %s. PriceDiff: %s %%'
                                % (mkt1["name"], mkt2["name"], round((mkt1["sell"]/mkt2["buy"] - 1) * 100, 4)))
                    # mkt1 作为卖方，mkt2作为买方
                    sell_mkt = mkt1['name']
                    # sell_price = mkt1['sell']*(1-self.slippage)
                    sell_price = mkt1['sell'] - self.slippages[mkt1['name']]
                    buy_mkt = mkt2['name']
                    # buy_price = mkt2['buy']*(1+self.slippage)
                    buy_price = mkt2['buy'] + self.slippages[mkt2['name']]

                elif mkt2["sell"]/mkt1["buy"] > max(1+this_thres, mkt1["sell"]/mkt2["buy"]) and (
                    mkt2["sell_o"] and mkt1["buy_o"]):
                    logger.info('satisfied price different between %s and %s. PriceDiff: %s %%'
                                % (mkt2["name"], mkt1["name"], round((mkt2["sell"]/mkt1["buy"] - 1) * 100, 4)))
                    # mkt2 作为卖方，mkt1作为买方
                    sell_mkt = mkt2['name']
                    # sell_price = mkt2['sell']*(1-self.slippage)
                    sell_price = mkt2['sell'] - self.slippages[mkt2['name']]
                    buy_mkt = mkt1['name']
                    # buy_price = mkt1['buy']*(1+self.slippage)
                    buy_price = mkt1['buy'] + self.slippages[mkt1['name']]

                else:
                    # print(mkt1["sell"]/mkt2["buy"], mkt2["sell"]/mkt1["buy"], this_thres)
                    priceDiff = mkt1["sell"]/mkt2["buy"] - 1 if (mkt1["sell"]/mkt2["buy"] - 1) >= 0 else mkt2["sell"]/mkt1["buy"]- 1
                    logger.info('No satisfied price different between %s and %s. PriceDiff: %s %%'
                                % (mkt1["name"], mkt2["name"], round(priceDiff*100, 4)))

                if sell_mkt and buy_mkt:
                    self.mkt[buy_mkt].q.put(
                        {'type': 'New order',
                         'price': buy_price,
                         'amount': self.initial_amount,
                         'side': 'buy',
                         'name': buy_mkt})
                    self.mkt[sell_mkt].q.put(
                        {'type': 'New order',
                         'price': sell_price,
                         'amount': self.initial_amount,
                         'side': 'sell',
                         'name': sell_mkt
                         })

                    # 查询时需要保证顺序
                    pair = "{}_{}".format(mkt1['name'], mkt2['name'])

                    sell_mkt_msg = self.mkt[sell_mkt].q_output.get()
                    # print('Maker sell_mkt_msg receive', sell_mkt_msg)
                    if sell_mkt_msg['order_id']:
                        self.active_orders[pair]['sell'] = {sell_mkt_msg['order_id']: sell_mkt}

                    buy_mkt_msg = self.mkt[buy_mkt].q_output.get()
                    # print('Maker buy_mkt_msg receive', buy_mkt_msg)
                    if buy_mkt_msg['order_id']:
                        self.active_orders[pair]['buy'] = {buy_mkt_msg['order_id']: buy_mkt}

if __name__ == '__main__':
    os.environ[Constants.DQUANT_ENV] = "dev"
    ticker_hb = TickerHeartbeats("SpotDiff")
    new_maker = NewMaker()
    t = time.time()
    tick = 0
    auditor = Audit(config_name)

    doctor = BlockAlarm(ticker_hb.q_hb)
    doctor.setDaemon(True)
    doctor.start()
    while True:
        t1 = time.time()
        m, s = divmod(t1 - t, 60)
        h, m = divmod(m, 60)
        logger.info("tick %d %02d:%02d:%02d" % (tick, h, m, s))
        ticker_hb.hb()
        auditor.check()
        new_maker.getAccount()
        new_maker.cancelActiveOrdersAndTake()
        new_maker.placeOrders()
        tick += 1
        # API访问限制，设置延时
        time.sleep(5)