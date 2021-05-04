import json
import os
import queue
import threading
import asyncio
from copy import copy
import sys
import logging
import time
from multiprocessing import Queue


curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
rootPath = os.path.split(rootPath)[0]
os.sys.path.append(rootPath)

from dquant.constants import Constants
from dquant.strategy.trigger import DepthIndexTrigger
from dquant.markets._okex_future_rest import OkexFutureRest
from dquant.markets._okex_future_ws import OkexFutureWs
from dquant.markets._okex_spot_ws_v2 import OkexSpotWs
from dquant.common.alarms import alarm_of_stock


logger = logging.getLogger("dquant")
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
fh = logging.FileHandler('../../logs/OKEXHedging.log', mode='w')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
logger.addHandler(fh)
logger.addHandler(ch)

# config_name = "configHedging.json"
#config_name = "../strategy/configHedging.json"

q_msg = Queue()


class TakersWs(threading.Thread):
    def __init__(self, mkt, meta_code, strategy_id, config_name="configHedging.json"):
        super(TakersWs, self).__init__()
        new = asyncio.new_event_loop()
        asyncio.set_event_loop(new)
        self.mkt = mkt(meta_code, loop=new)
        self.mkt.strategy_id = strategy_id
        self.mkt.trigger = True
        self.base_coin = self.mkt.base_currency
        self.target_coin = self.mkt.market_currency
        self.minimum_amount = self.mkt.minimum_amount
        self.name = self.mkt.name
        self.fee_rate = self.mkt.fee_rate
        self.q = queue.Queue()
        self.q_output = queue.Queue()
        self.mkt.setDaemon(True)
        self.mkt.start()
        self.c = 0
        self.error_c = 0
        self.accumulative_amount = 0
        self.total_filled = 0
        # 列队状态
        self.status = True
        # 交易所状态 是否可用
        self.available = True
        self.config = json.load(open(config_name, 'r'))
        self.max_task_on_do = self.config["max_task_on_do"]
        self.minimum_amount = self.config[meta_code]["minimum_amount"]
        self.taker_action = {"long": self.mkt_sell, "short": self.mkt_buy,
                             "sell": self.mkt_sell, "buy": self.mkt_buy}

    def check_task_done(self):
        task_on_do = self.q.qsize() + self.c
        if not self.status or (not task_on_do and not self.accumulative_amount):
            return True
        else:
            return False

    def check_task_on_do(self):
        if not self.status:
            logger.warning("Blocking the thread")
        task_on_do = self.q.qsize() + self.c
        if task_on_do >= self.max_task_on_do:
            logger.warning('Taker(%s) task on do: %s' % (self.name, task_on_do))
            self.status = False
        else:
            self.status = True

    def getDepth(self):
        try:
            depth = self.mkt.getDepth()
            return depth
        except TimeoutError:
            self.available = False
            return None

    def parse_meta(self, meta_code):
        self.mkt.parse_meta(meta_code)

    def mkt_sell(self, total_price):
        depth = self.getDepth()
        ref_price = (depth['bids'][0]['price'] + depth['asks'][0]['price']) / 2
        res = self.mkt.sell(amount=total_price/ref_price)
        return res

    def mkt_buy(self, total_price, reference_price):
        res = self.mkt.sell(total_price)
        return res

    def run(self):
        while True:
            self.check_task_on_do()
            m = self.q.get()
            side = m['side']
            logger.debug('Taker get message: %s' % m)
            total_price = float(m.get('total_price'))
            # 定价模型，这里先用买一价作为目标价格，因此amount=total_price/bid_price
            depth = self.getDepth()
            ref_price = (depth['bids'][0]['price'] + depth['asks'][0]['price']) / 2
            amount_to_be_filled = total_price / ref_price + self.accumulative_amount
            # BTC 数量大于等于0.01 / LTC 数量大于等于0.1 / ETH 数量大于等于0.01
            if amount_to_be_filled >= self.minimum_amount:
                logger.info("Taker get message from maker: %s, real amount is %s." % (m, amount_to_be_filled))
                result = None
                self.c += 1
                try:
                    result = self.taker_action[side](total_price)
                    logger.debug("Taker result: %s" % result)
                    if result and "order_id" in result:
                        order_id = result['order_id']
                        taker_side = "buy" if side == 'short' else "sell"
                        logger.info('Okex Spot: Taker order(%s) %s, total_price %s' % (order_id, taker_side, total_price))
                        self.accumulative_amount = 0
                        self.total_filled += total_price
                        self.q_output.put(result)
                    else:
                        logger.error('Okex Spot ERROR: %s' % result)
                        self.error_c += 1
                        self.q.put(m)
                except Exception as ex:
                    logger.error('Okex Spot ERROR(%s): %s' % (ex, result))
                    self.error_c += 1
                    self.q.put(m)
                finally:
                    self.c -= 1
                    # 某个Taker报错超过5次
                    if self.error_c >= 5:
                        logger.critical("Fatal Error: Taker %s seems not working properly, exit" % self.name)
                        self.q_output.put({})
                        self.status = False
                        break
            else:
                logger.info("%s is less than minimum amount: %s" % (amount_to_be_filled, self.minimum_amount))
                self.accumulative_amount += amount_to_be_filled
                self.total_filled += total_price


class OkexSpotWsTaker(TakersWs):
    def __init__(self, meta_code, strategy_id):
        super(OkexSpotWsTaker, self).__init__(OkexSpotWs, meta_code, strategy_id)


class Okex_Future(threading.Thread):
    def __init__(self, meta_code, strategy_id):
        super(Okex_Future, self).__init__()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.okex = OkexFutureWs(meta_code, self.loop)
        self.name = self.okex.name
        self.okex_rest = OkexFutureRest(meta_code)
        self.okex.strategy_id = strategy_id
        # self.q_trigger = self.okex.q_trigger
        self.q_order_result = self.okex.q_order_result
        self.okex.start()

        self.last_get_order_info = {'order_id':None, 'amount_filled': None}
        self.lastPosition = 0
        self.q = queue.Queue()
        self.q_output = queue.Queue()
        self.order = [None, '']
        self.order_id = None
        self.side = ''
        self.meta_code = meta_code

    def reset(self):
        self.order = [None, '']
        self.order_id = None
        self.side = ''

    def get_latest_order(self, side):
        # 查询买卖订单
        hist = self.okex.getHist()
        temp_hist = copy(hist)
        # 从最近成交/成功删除的订单开始遍历
        latest_order_id, latest_order_details = temp_hist[side].popitem()
        return {'order_id':latest_order_id, 'details': latest_order_details}

    def my_getOrder(self, order_id):
        # 初始化返回结果
        order_details = self.okex.getOrder(order_id)
        amount_filled = order_details['deal_amount']
        amount_orig = order_details['amount']
        price = order_details['price']
        side = order_details['type']
        ret = {'order_id': order_id, 'price': price, 'amount_filled': amount_filled, 'amount_orig': amount_orig, 'side': side}
        return ret

    def run(self):
        while True:
            m = self.q.get()

            if m['type'] in ['Initial long order', 'Initial short order']:
                q_msg.put({'meta_code': self.meta_code, 'type': m['type'].split(' ')[1]})

            if m['type'] == 'Initial long order':
                amount = m['amount']
                future_depth = self.okex.getDepth()
                future_bid_price = future_depth['bids'][0]['price']
                result = self.okex.long(amount=amount, price=future_bid_price)
                # self.order_id = result['order_id']
                self.order = [result['order_id'], 'long']
                logger.info('Long Order: id %s @%s' % (result['order_id'], future_bid_price))
                self.q_output.put(result)
                # self.loop.call_soon_threadsafe(self.q_output.put_nowait, result)

            elif m['type'] == 'Initial short order':
                amount = m['amount']
                future_depth = self.okex.getDepth()
                future_ask_price = future_depth['asks'][0]['price']
                result = self.okex.short(amount=amount, price=future_ask_price)
                # self.order_id = result['order_id']
                self.order = [result['order_id'], 'short']
                logger.info('Short Order: id %s @%s' % (result['order_id'], future_ask_price))
                self.q_output.put(result)

            elif m['type'] == 'Get order':
                ret = self.my_getOrder(self.order[0])
                # details = ret
                order_id = ret['order_id']
                amount_filled = ret['amount_filled']
                amount_orig = ret['amount_orig']
                if amount_orig:
                    self.lastPosition = amount_orig - amount_filled
                    # 控制输出，与上次相同的数据就不用输出了
                    last_id = self.last_get_order_info['order_id']
                    last_amount_filled = self.last_get_order_info['amount_filled']
                    if last_id != ret['order_id'] or last_amount_filled != amount_filled:
                        self.last_get_order_info['order_id'] = ret['order_id']
                        self.last_get_order_info['amount_filled'] = amount_filled
                        logger.info('GetOrder: id %s, filled: %s' % (ret['order_id'], amount_filled))
                # 查不到订单，输出一下成交数量，结束循环
                else:
                    try:
                        latest_executed_order = self.get_latest_order(side=self.order[1])
                        amount_filled = latest_executed_order['details']['deal_amount']
                        amount_orig = latest_executed_order['details']['amount']
                        amount_remain = amount_orig - amount_filled
                        self.lastPosition = amount_remain             # 正常情况下是0
                        logger.info('GetOrder: id %s, filled: %s' % (latest_executed_order['order_id'], amount_filled))
                        break
                    except Exception as ex:
                        logger.error('GetOrder: %s' % ex)

                ret['amount_filled'] = amount_filled
                self.q_output.put(ret)
                # self.loop.call_soon_threadsafe(self.q_output.put_nowait, ret)

            elif m['type'] == 'Delete and place new order':

                ret = self.my_getOrder(self.order_id[0])
                #   待下单信息
                price = m['price']
                side = m['side']
                # 待删除订单信息
                order_id = ret['order_id']

                # 删除订单
                # 订单状态未完成（可以查到订单号）
                if order_id:
                    self.okex.deleteOrder(order_id)
                    result = self.okex.getOrder(order_id)
                    amount_filled = result['deal_amount']
                    amount_orig = result['amount']
                    # amount_remain = amount_orig - amount_filled
                    self.lastPosition = amount_orig - amount_filled
                    old_price = result['price']
                    logger.info('Delete: canceling order %s @%s, filled %s, last position: %s' % (order_id, old_price, amount_filled, self.lastPosition))
                # 订单已完成
                else:
                    latest_executed_order = self.get_latest_order(side='long')
                    amount_filled = latest_executed_order['details']['deal_amount']
                    amount_orig = latest_executed_order['details']['amount']
                    amount_remain = amount_orig - amount_filled
                    self.lastPosition = amount_remain  # 正常情况下是0
                    logger.info('Delete: id %s has been filled before deleted, amount: %s ' % (latest_executed_order['order_id'], amount_filled))
                    break

                # 下单， 数量是删除订单时返回的
                amount = self.lastPosition
                if side == 'long':
                    res = self.okex.long(amount=amount, price=price)
                else:
                    res = self.okex.short(amount=amount, price=price)
                # self.order_id = res['order_id']
                self.order[0] = res['order_id']
                order = self.okex.getOrder(res['order_id'])
                logger.info('Place order: %s: amount %s' % (order['order_id'], order['amount']))
                message = {'type': 'Order new', 'order_id': order['order_id'], 'amount': order['amount']}
                self.q_output.put(message)
                # self.loop.call_soon_threadsafe(self.q_output.put_nowait, message)

            elif m['type'] == 'Close order':
                self.okex.deleteOrder(self.order_id[0])
                if self.order_id[1] == 'long':
                    self.okex_rest.close_all_long_orders()
                else:
                    self.okex_rest.close_all_short_orders()


class Hedging(threading.Thread):
    def __init__(self, config_name="configHedging.json"):
        super(Hedging, self).__init__()
        self.config = json.load(open(config_name, 'r'))
        self.meta_code_spot = self.config['meta_code_spot']
        self.meta_code_future = self.config['meta_code_future']
        self.initial_amount = self.config['initial_amount']
        self.strategy_id = self.config['strategy_id']
        self.trigger_amount = self.config['trigger_amount']
        self.trigger_order_premium = self.config['trigger_order_premium']
        self.trigger_close_premium = self.config['trigger_close_premium']
        self.spot_mkt = None
        self.future_mkt = None
        self.generateObj()
        self.no_task = False
        self.reference_bid_price = None
        self.order_record = {}
        self.trigger =DepthIndexTrigger.Q_TRIGGER

        self.depths = {self.spot_mkt.name: {}, self.future_mkt.name: {}}

        self.makerThread = threading.Thread(target=self.maker)
        self.makerThread.setDaemon(True)
        self.makerThread.start()

    def generateObj(self):
        self.spot_mkt = OkexSpotWsTaker(self.meta_code_spot, strategy_id=self.strategy_id)
        self.spot_mkt.setDaemon(True)
        self.spot_mkt.start()
        self.future_mkt = Okex_Future(self.meta_code_future, strategy_id=self.strategy_id)
        self.future_mkt.setDaemon(True)
        self.future_mkt.start()

    def _has_future_order(self):
        return self.future_mkt.order_id

    def get_amount_filled_and_orig(self):
        amount_orig = 0
        amount_filled = 0
        if self.order_record:
            for order_id, details in self.order_record.items():
                amount_filled += details[0]
                amount_orig += details[1]
        return amount_filled, amount_orig

    def run(self):
        count = 0
        # 当成交trigger_amount单位期货，触发现货买入/卖出trigger_amount*100等价的BTC
        # trigger_amount = 1
        while True:
            # 订单更新信息来驱动策略
            # message = {'order_id': order_id,'amount_orig': amount,'amount_filled': deal_amount,'message_type': 'order update'}
            message = self.future_mkt.q_order_result.get()
            # print(message)
            if not self.future_mkt.order_id:
                continue
            self.order_record.update({message['order_id']: [message['amount_filled'], message['amount_orig']]})
            # self.last_order['order_id'] = message
            side = message['side']
            amount_filled, amount_orig = self.get_amount_filled_and_orig()
            amount_remain = amount_orig - amount_filled
            # 余下额度不满足taker最小交易额的时候，等待最后全部成交
            if side == "long":
                reference_price = self.depths[self.spot_mkt.name]['bids'][0]['price']
            else:
                reference_price = self.depths[self.spot_mkt.name]['asks'][0]['price']
            if amount_remain and amount_remain * 100 / reference_price < self.spot_mkt.minimum_amount:
                logger.info("Future amount_remain: %s" % amount_remain)
                continue

            # 如果订单数量已经不足以触发策略，raise AssertException
            # assert self.trigger_amount * count <= amount_orig

            if amount_filled >= self.trigger_amount:
                # 如果一次成交5，trigger为2，则应该触发2倍的现货卖出， 因为得到的是累计成交量，需要减去过去成交过的数量
                times = amount_filled // self.trigger_amount - count
                # BTC 100USD/张, ETH 10USD/张
                # 触发次数*每次卖出的数量*100
                total_price = times * self.trigger_amount * 100
                self.spot_mkt.q.put({'total_price': total_price, "side": side})
                count = amount_filled // self.trigger_amount
                # self.spot_mkt.q_output.get()

            if amount_filled == amount_orig:
                logger.info('The order has done')
                while True:
                    logger.debug("check_task_done:%s; total_filled: %s, initial: %s" % (self.spot_mkt.check_task_done(), self.spot_mkt.total_filled, self.initial_amount))
                    if (self.spot_mkt.check_task_done() and self.spot_mkt.total_filled == self.initial_amount*100) or not self.spot_mkt.status:
                        self.no_task = True
                    time.sleep(1)

    def close_contract(self):
        pass

    def maker(self):
        # self.future_mkt.q.put({'type': 'Initial long order', 'amount': self.initial_amount})
        # self.future_mkt.q_output.get()
        while True:
            # 期货市场Depth/index/现货Depth更新信息来驱动策略
            # message = {"asks": list_of_ask, 'bids': list_of_bid, "name": self.name}
            # message = self.future_mkt.q_trigger.get()
            message = self.trigger.get()
            # 更新深度表
            self.depths[message["name"]] = message
            # 期货指数、期货价格、现货指数都已获取到
            if len(self.depths) < 3:
                logger.info("Got market info from %s, %s/3" % (self.depths.keys(), len(self.depths)))
                continue
            # 计算升贴水
            index = self.depths["{}_index".format(self.future_mkt.name)]["futureIndex"]
            future_bid0 =self.depths[self.future_mkt.name]['bids'][0]['price']
            future_ask0 =self.depths[self.future_mkt.name]['asks'][0]['price']
            spot_bid0 = self.depths[self.spot_mkt.name]['bids'][0]['price']
            spot_ask0 = self.depths[self.spot_mkt.name]['asks'][0]['price']

            spot_price = (spot_bid0 + spot_ask0) / 2
            premium = (index - spot_price) / spot_price
            print("premium: %s" % premium)
            # self.reference_bid_price = float(message['bid_price'])
            # print(message)

            # 当前状态无订单
            if premium >= self.trigger_order_premium and not self._has_future_order():
                logger.info("premium: %s" % premium)
                # 升水的时候期货做空，现货做多
                self.future_mkt.q.put({'type': 'Initial short order', 'amount': self.initial_amount})
                self.future_mkt.q_output.get()
                self.future_side = 'long'
                logger.info("Open long position %s" % self.initial_amount)
            elif premium <= - self.trigger_order_premium and not self._has_future_order():
                logger.info("premium: %s" % premium)
                # 贴水的时候期货做多，现货做空
                self.future_mkt.q.put({'type': 'Initial long order', 'amount': self.initial_amount})
                self.future_mkt.q_output.get()
                self.future_side = 'short'
                logger.info("Open short position %s" % self.initial_amount)

            # 当前状态有订单
            if - self.trigger_close_premium <= premium <= self.trigger_close_premium and self._has_future_order():
                logger.info("premium: %s" % premium)
                # 平仓
                self.future_mkt.q.put({'type': 'Close order'})
                self.future_mkt.q_output.get()
                side = "buy" if self.future_mkt.order[1] == "long" else "sell"
                amount_filled, amount_orig = self.get_amount_filled_and_orig()
                total_price = amount_filled
                self.spot_mkt.q.put({'total_price': total_price, "side": side})
                self.future_mkt.reset()
                logger.info("Close position.")

            if not self._has_future_order():
                continue

            # 获取当前订单信息
            self.future_mkt.q.put({'type': 'Get order'})
            m = self.future_mkt.q_output.get()
            my_price = m['price']
            side = m['side']

            if m['amount_orig'] == m['amount_filled']:
                logger.info('The order has been filled')
                break
            if side == 'long':
                # assert m['amount_filled'] < initial_amount
                if my_price and future_bid0 > my_price:
                    amount = m['amount_orig'] - m['amount_filled']
                    self.future_mkt.q.put({'type': 'Delete and place new order', 'price': future_bid0, "side":side})
                    logger.info('Delete and place new order: Long %s @%s, past: @%s' % (amount, future_bid0, my_price))
                    self.future_mkt.q_output.get()
            else:
                if my_price and future_ask0 < my_price:
                    amount = m['amount_orig'] - m['amount_filled']
                    self.future_mkt.q.put({'type': 'Delete and place new order', 'price': future_ask0, "side":side})
                    logger.info('Delete and place new order: Short %s @%s, past: @%s' % (amount, future_ask0, my_price))
                    self.future_mkt.q_output.get()

def create_hedging_process(amount, future_meta, spot_meta):
    logger.info("Hedging Program get task: amount: %s, future: %s, spot: %s" % (amount, future_meta, spot_meta))
    okexHedge = Hedging()
    okexHedge.start()
    # okexHedge.join()
    while True:
        if okexHedge.no_task:
            logger.info('End of process')
            sys.exit()


def hedge():

    okexHedge = Hedging()
    okexHedge.start()
    okexHedge.join()

def hedge_eth():
    okexHedge = Hedging()
    okexHedge.start()
    okexHedge.join()

def hAlarm():

    msg = q_msg.get()
    mtype = msg['type']

    okex_rest = OkexFutureRest(msg['meta_code'])
    okex_rest.start()

    while True:

        cur_bao = okex_rest.get_current_and_baocang_price()
        success = alarm_of_stock(cur_bao['current_price'], cur_bao['baocang_price'], mtype)
        if success:
            print('爆仓报警发出去了。只报一次哦！')
            break


if __name__ == "__main__":
    os.environ[Constants.DQUANT_ENV] = "dev"
    # tasks = [hAlarm, hedge]
    #
    # from multiprocessing import Pool
    # p = Pool(2)
    # for task in tasks:
    #     p.apply_async(task, args=())
    # p.close()
    # p.join()

    okexHedge = Hedging()
    okexHedge.start()
    okexHedge.join()
