import os
import sys
import threading

from copy import copy

sys.path.append('../../')
import urllib
import asyncio
import json
import logging
import collections
import queue
from dquant.config import cfg
from dquant.constants import Constants
from dquant.markets.market import Market
import requests, hmac, hashlib, time
from dquant.util import Util
import websockets
from dquant.common.email_send import send

logger = logging.getLogger(__name__)

class BitfinexSpotWs(Market):
    def __init__(self, meta_code, loop):
        market_currency, base_currency, symbol = self.parse_meta(meta_code)
        super().__init__(market_currency, base_currency, meta_code, cfg.get_float_config(Constants.BITFINEX_FEE))
        self.apikey = cfg.get_config(Constants.BITFINEX_APIKEY)
        self.apisec = cfg.get_config(Constants.BITFINEX_APISEC)
        self.base_url = Constants.BITFINEX_SPOT_WS_BASE
        self.bitfinex_id = cfg.get_config(Constants.BITFINEX_ID)
        self.strategy_id = cfg.get_config(Constants.BITFINEX_STRATEGY_ID)
        self.fee_rate_taker = cfg.get_float_config(Constants.BITFINEX_FEE_TAKER)
        self.symbol = symbol
        self.name = 'Bitfinex'
        # 取精度，如果取不到，就使用默认值。
        # ['min_amount', 'price', 'amount']
        [self.minimum_amount, self.price_precision, self.amount_precision] = cfg.get_precisions(self.name, market_currency+base_currency)
        if not (self.price_precision and self.amount_precision):
            self.minimum_amount = cfg.get_float_config(Constants.BITFINEX_MINIMUM_AMOUNT)
            self.amount_precision = cfg.get_int_config(Constants.BITFINEX_AMOUNT_PRECISION)
            self.price_precision = cfg.get_int_config(Constants.BITFINEX_PRICE_PRECISION)
        # self.timeout = Constants.OK_HTTP_TIMEOUT
        # 延长timeout的时间
        self.timeout = 30
        self.partially_filled_orders = {}
        self.position = {}
        self.depth = {}
        self.depth_lock = threading.Lock()
        self.depth_new = {"asks":{}, "bids":{}}
        self.orders = {}
        self.unique_te = []
        self.wallet = {'exchange': {}, 'funding': {}}
        self.on_deleting = None
        self.q = asyncio.Queue()
        self.order_result_required = False
        self.q_order_result = queue.Queue()
        self.hist = {'buy': collections.OrderedDict(), 'sell': collections.OrderedDict()}
        self.hist_lenth = 10
        # 不同的gid以便程序分辨各自的订单
        self.ip_pid_sid = Util.bfx_get_gid(self.strategy_id)
        self.gid = self.ip_pid_sid['gid']
        # print(self.gid)
        self.cid_dict = {}
        self.cid_lock = threading.Lock()
        self.websocket = None
        self.session = requests.session()
        self.loop = loop  # type: AbstractEventLoop
        self.static_methods_register()
        self.depth_chanID = None

    def _getnonce(self):
        return int(time.time() * 1000000)

    async def _close_ws(self):
        await asyncio.sleep(5)
        await self.websocket.close()

    async def sub_channel(self):
        # sub depth
        while True:
            if self.websocket and self.websocket.open:
                auth_payload = 'AUTH{}'.format(self._getnonce())
                message = [{'event': 'subscribe', 'channel': 'book', 'symbol': self.symbol, 'prec': 'P0', 'freq': 'F0', 'len': '25'},
                           {'apiKey': self.apikey, 'event': 'auth','authPayload': auth_payload,'authNonce': self._getnonce(),
                            'authSig': hmac.new(self.apisec.encode(), msg=auth_payload.encode(),digestmod=hashlib.sha384).hexdigest()}]
                for m in message:
                    await self.websocket.send(json.dumps(m))
                break

    def unsub_channel_message(self, chanID):
        message = {"event": "unsubscribe", "chanId": chanID}
        return json.dumps(message)

    def resub_depth_channel(self):
        logger.debug("Bitfinex unsub depth channel")
        unsub_m = self.unsub_channel_message(self.depth_chanID)
        self.loop.call_soon_threadsafe(self.q.put_nowait, unsub_m)
        resub_m_raw = {'event': 'subscribe', 'channel': 'book', 'symbol': self.symbol, 'prec': 'P0', 'freq': 'F0', 'len': '25'}
        self.depth = {}
        logger.debug("Bitfinex resub depth channel")
        resub_m = json.dumps(resub_m_raw)
        self.loop.call_soon_threadsafe(self.q.put_nowait, resub_m)

    def bitfinex_depth_format(self, result):
        try:
            # update
            if len(result[1]) == 3:
                # delete
                if result[1][1] == 0:
                    try:
                        del self.depth[result[1][0]]
                    except:
                        pass
                else:
                    self.depth[result[1][0]] = result[1][2]
            # new data: [chanID,[[p,c,a],[p,c,a],...]]
            else:
                for each_item in result[1]:
                    self.depth[each_item[0]] = each_item[2]
        except Exception as ex:
            self.error('depth format: %s' % ex)
    # def depth_update(self, l):
    #     '''
    #     subscribe to channel
    #     if AMOUNT > 0 then bid else ask; Funding: if AMOUNT < 0 then bid else ask
    #     receive the book snapshot and create your in-memory book structure
    #     when count > 0 then you have to add or update the price level
    #         3.1 if amount > 0 then add/update bids
    #         3.2 if amount < 0 then add/update asks
    #     when count = 0 then you have to delete the price level.
    #         4.1 if amount = 1 then remove from bids
    #         4.2 if amount = -1 then remove from asks
    #     :param l: list[PRICE,COUNT,AMOUNT]
    #     :return:
    #     '''
    #     try:
    #         price = l[0]
    #         count = l[1]
    #         amount = l[2]
    #         if count > 0:
    #             if amount > 0:
    #                     self.depth_new['bids'].update({price: abs(amount)})
    #             if amount < 0:
    #                     self.depth_new['asks'].update({price: abs(amount)})
    #         if count == 0:
    #             if amount == 1:
    #                     del self.depth_new['bids'][price]
    #             if amount == -1:
    #                     del self.depth_new['asks'][price]
    #     except Exception as ex:
    #         logger.error("Bitfinex update depth %s" % ex)

    # def bitfinex_depth_format(self, result):
    #     try:
    #         with self.depth_lock:
    #             # update
    #             if len(result[1]) == 3:
    #                 self.depth_update(result[1])
    #             # new data: [chanID,[[p,c,a],[p,c,a],...]]
    #             else:
    #                 for each_item in result[1]:
    #                     self.depth_update(each_item)
    #     except Exception as ex:
    #         self.error('depth format: %s' % ex)

    def getDepth(self):
        error_c = 0
        while True:
            if not self.depth:
                self.error('Bitfinex: getDepth: None, Retry')
                error_c += 1
                if error_c >= 5:
                    raise TimeoutError
                time.sleep(5)
                continue
            ret = dict(bids=[], asks=[])
            temp_depth = copy(self.depth)
            for p, a in temp_depth.items():
                if float(a) > 0:
                    ret['bids'].append({
                        'price': float(p),
                        'amount': float(a)
                    })
                else:
                    ret['asks'].append({
                        'price': float(p),
                        'amount': float(-a)
                    })
            ret['bids'].sort(key=lambda item: item['price'], reverse=True)
            ret['asks'].sort(key=lambda item: item['price'], reverse=False)

            # 买卖报价数量小于20个，则更新出现错误
            if len(ret['bids']) <= 22 or len(ret['asks']) <= 22:
                self.error('Bitfinex: getDepth: abnormal length, Retry')
                error_c += 1
                self.resub_depth_channel()
                if error_c >= 5:
                    raise TimeoutError
                time.sleep(5)
                continue

            return ret
    #
    # def getDepth(self):
    #     error_c = 0
    #     while True:
    #         if not self.depth_new['asks'] or not self.depth_new['bids']:
    #             self.error('Bitfinex: getDepth: None, Retry')
    #             error_c += 1
    #             if error_c >= 5:
    #                 raise TimeoutError
    #             time.sleep(5)
    #             continue
    #         ret = dict(bids=[], asks=[])
    #         with self.depth_lock:
    #             for p, a in self.depth_new['bids'].items():
    #                 ret['bids'].append({
    #                     'price': float(p),
    #                     'amount': float(a)
    #                 })
    #             for p, a in self.depth_new['asks'].items():
    #                 ret['asks'].append({
    #                     'price': float(p),
    #                     'amount': float(a)
    #                 })
    #         ret['bids'].sort(key=lambda item: item['price'], reverse=True)
    #         ret['asks'].sort(key=lambda item: item['price'], reverse=False)
    #
    #         # 买卖报价数量小于20个，则更新出现错误
    #         if len(ret['bids']) <= 22 or len(ret['asks']) <= 22:
    #             self.error('Bitfinex: getDepth: abnormal length, Retry')
    #             error_c += 1
    #             self.resub_depth_channel()
    #             if error_c >= 5:
    #                 raise TimeoutError
    #             time.sleep(5)
    #             continue
    #         return ret

    def getAccount(self, coin=[]):
        ret = {'exchange':{}, 'funding':{}}
        for wallet, wallet_snapshot in self.wallet.items():
            ans = {}
            # 对于每个钱包下的币种
            for c in coin:
                if c in wallet_snapshot:
                    # ans[c] = wallet_snapshot[c]
                    ans[c] = wallet_snapshot[c][2]
                else:
                    ans[c] = 0.0
                    # ans[c] = [None, c, 0.0, 0.0, None]
            ret[wallet] = ans
        return ret

    def static_methods_register(self):
        self.methods["book"] = self.update_depth
        self.methods["ws"] = self.update_wallet
        self.methods["wu"] = self.update_wallet
        self.methods["ps"] = self.update_position
        self.methods["os"] = self.update_order
        self.methods["on"] = self.update_order
        self.methods["ou"] = self.update_order
        self.methods["te"] = self.update_order
        self.methods["n"] = self.update_notification
        # 成交订单或者取消订单
        self.methods["oc"] = self.update_execution


    # 注册函数，用完删除
    def register_callbacks(self):
        self.methods["book"] = self.update_depth
        self.methods["execution"] = self.update_execution
        self.methods["position"] = self.update_position

    def remove_callbacks(self):
        pass
        # del self.methods["book"]

    # 更新depth，并且更新flag状态
    async def update_depth(self, depth_data):
        if isinstance(depth_data, dict) and depth_data['event'] != 'error':
            self.methods[depth_data['chanId']] = self.update_depth
            self.depth_chanID = depth_data['chanId']
        else:
            self.bitfinex_depth_format(depth_data)
            # self.update_flags["depth"] = True

    async def update_wallet(self, wallet_data):
        if wallet_data[1] == 'ws':
            for item in wallet_data[-1]:
                if item[0] in ['exchange', 'funding']:
                    wallet = item[0]
                    self.wallet[wallet][item[1]] = item
        else:
            wallet = wallet_data[-1][0]
            self.wallet[wallet][wallet_data[-1][1]] = wallet_data[-1]
        # self.update_flags["wallet"] = True

    async def update_position(self, positioin_data):
        # 仓位数据未作处理
        self.position = positioin_data[-1]
        self.update_flags["position"] = True

    def _exists_in_unique_te(self, te_id, order_id):
        if [te_id, order_id] in self.unique_te:
            # 重复的trade data
            return True
        else:
            return False

    def _puts_in_unique_te(self, te_id, order_id):
        if len(self.unique_te) >= 50:
            self.unique_te.pop(0)
        self.unique_te.append([te_id, order_id])

    async def update_order(self, order_data):
        details = {}
        if order_data[1] == 'os':
            for item in order_data[-1]:
                # Order Status: ACTIVE, EXECUTED, PARTIALLY FILLED, CANCELED
                status = item[13]
                amount_remain = item[6]
                amount_orig = item[7]
                if item[1] == self.gid:
                    item.append(0)
                    item.append(amount_orig-amount_remain)
                    details[item[0]] = item
            self.orders = details
            self.partially_filled_orders = details
            self.update_flags["order"] = True

        # trade update
        elif order_data[1] == 'te':
            # print(order_data)
            # logger.debug("Bitfinex te: %s" % order_data)
            trade_id = order_data[-1][0]
            order_id = order_data[-1][3]
            if self._exists_in_unique_te(trade_id, order_id):
                return
            self._puts_in_unique_te(trade_id, order_id)
            amount_filled = order_data[-1][4]
            price = float(order_data[-1][5])
            order_time = order_data[-1][2]
            side = 'buy' if amount_filled > 0 else 'sell'
            # print(self.orders)
            if order_id in self.orders:
                logger.debug("Bitfinex te: %s" % order_data)
                # amount_filled_this_time amount_fill_total
                # self.orders[order_id][-2] = amount_filled
                self.orders[order_id][-1] += amount_filled
                amount_orig = self.orders[order_id][7]
                amount_remain = round(amount_orig - self.orders[order_id][-1], 10)
                # self.orders[order_id][6] = amount_remain
                account_id = self.orders[order_id][1]

                q_message = {'order_id': order_id, 'amount_orig': abs(amount_orig), 'amount_remain': abs(amount_remain), "price": price,
                             'amount_filled_this_time': abs(amount_filled), 'trade_pair': self.symbol[1:], 'order_time': order_time,
                             'side': side,'account_id': account_id, 'timestamp': int(time.time() * 1000), 'platform_id': 'bitfinex'}
                # print(q_message)
                if self.order_result_required:
                    logger.debug("Bitfinex q_order_result %s" % q_message)
                    self.q_order_result.put(q_message)
                # print(self.q_order_result.qsize())
                # 完全成交
                if not amount_remain:
                    del self.orders[order_id]

        elif order_data[1] == 'on':
            if order_data[-1][1] == self.gid:
                detail = order_data[-1]
                amount_fill_total = 0
                amount_fill_this_time = 0
                detail.append(amount_fill_total)
                detail.append(amount_fill_this_time)
                self.orders[order_data[-1][0]] = detail
        else:
            pass

    async def update_notification(self, ntf_data):
        status = ntf_data[-1][-2]
        # if not status or status != 'SUCCESS':
        #     logger.info("Order: %s" % ntf_data[-1][-1])
        # 交易所收到新订单\取消订单回执
        # if ntf_data[-1][1] == 'on-req' or ntf_data[-1][-1] == 'Order not found.':
        # if ntf_data[-1][1] == 'on-req' and status == 'SUCCESS' and ntf_data[-1][4][2] == self.cid:
        if ntf_data[-1][1] == 'on-req' and status == 'SUCCESS' and ntf_data[-1][4][2] in self.cid_dict:
            logger.debug('Bitfinex Notification: %s' % ntf_data)
            detail = ntf_data[-1][4]
            amount_fill_this_time = 0
            amount_fill_total = 0
            detail.append(amount_fill_total)
            detail.append(amount_fill_this_time)
            self.orders[ntf_data[-1][4][0]] = ntf_data[-1][4]
            # print(self.orders)
            self.new_order_result = ntf_data[-1][4]
            if self.cid_dict[ntf_data[-1][4][2]]:
                self.update_flags["new_order_result"] = True
            else:
                self.deleteOrder(ntf_data[-1][4][0])
            with self.cid_lock:
                self.cid_dict.pop(ntf_data[-1][4][2])
        # elif ntf_data[-1][1] == 'on-req' and ntf_data[-1][4][2] == self.cid:
        elif ntf_data[-1][1] == 'on-req' and ntf_data[-1][4][2] in self.cid_dict:
            logger.debug('Bitfinex Notification: %s' % ntf_data)
            if ntf_data[-1][-1].startswith('Invalid order: not enough exchange balance'):
                account_balance = self.getAccount(coin=[self.market_currency, self.base_currency])['exchange']
                self.error('Bitfinex New order: %s, exchange balance: %s' % (ntf_data[-1][-1], account_balance))
                self.new_order_result = account_balance
                if self.cid_dict[ntf_data[-1][4][2]]:
                    self.update_flags["new_order_result"] = True
                else:
                    self.deleteOrder(ntf_data[-1][4][0])
                with self.cid_lock:
                    self.cid_dict.pop(ntf_data[-1][4][2])

        if ntf_data[-1][1] == 'oc-req' and status == 'ERROR':
            order_id = ntf_data[-1][4][0]
            if order_id == self.on_deleting:
                logger.info("Order not found: %s" % ntf_data)
                self.delete_result = ntf_data[-1]
                self.update_flags["delete_result"] = True
        # self.update_flags["notification"] = True

    async def update_execution(self, exec_data):
        status = exec_data[-1][13]
        gid = exec_data[-1][1]
        # if status.startswith('EXECUTED') or status.startswith('CANCELED'):
        if gid == self.gid:
            logger.debug('Bitfinex execution: %s' % exec_data)
            if status.startswith('CANCELED'):
                # print(exec_data)
                self.delete_result = exec_data[-1]
                self.update_flags["delete_result"] = True
                try:
                    amount_orig = exec_data[-1][7]
                    amount_remain = exec_data[-1][6]
                    if amount_orig != amount_remain:
                        order_id = exec_data[-1][0]
                        simple_side = 'buy' if exec_data[-1][7] > 0 else 'sell'
                        side_l = exec_data[-1][8].lower().split(' ')
                        side = "{} {}".format(simple_side, side_l[-1])
                        amount_filled = abs(exec_data[-1][7] - exec_data[-1][6])
                        order_time = exec_data[-1][5]
                        price = exec_data[-1][17]
                        fee_rate = self.fee_rate_taker if side.find('market') != -1 else self.fee_rate

                        if side == 'buy':
                            fee = '{}_{}'.format('%.8f' % (float(amount_filled) * float(fee_rate)), self.market_currency)
                        else:
                            fee = '{}_{}'.format('%.8f' % (float(amount_filled) * float(price) * fee_rate), self.base_currency)

                        data_store = Util.build_order_store(order_id=order_id, side=side, trade_pair=self.symbol[1:],
                            price=price, amount_filled=amount_filled, time_stamp=order_time,
                            client_order_id=self.gid, platform_name='bitfinex', platform_account_id=self.bitfinex_id,
                            strategy_id=self.strategy_id, fee=fee)
                        # print('data_store', data_store)
                        self.q_orders.put(data_store)
                        self.hist[simple_side][exec_data[-1][0]] = exec_data[-1]

                        if len(self.hist[simple_side]) > self.hist_lenth:
                            self.hist[simple_side].popitem(last=False)
                    del self.orders[exec_data[-1][0]]
                except Exception as ex:
                    self.error("Bitfinex recording canceled order: %s" % ex)

                # del self.orders[exec_data[-1][0]]
            # elif status.startswith('PARTIALLY FILLED'):
            #     self.orders[exec_data[-1][0]] = exec_data[-1]
            elif status.startswith('EXECUTED'):
                # print(exec_data)
                simple_side = 'buy' if exec_data[-1][7] > 0 else 'sell'
                side_l = exec_data[-1][8].lower().split(' ')
                side = "{} {}".format(simple_side, side_l[-1])
                order_id = exec_data[-1][0]
                account_id = exec_data[-1][1]
                amount_orig = exec_data[-1][7]
                amount_remain = exec_data[-1][6]
                amount_filled = abs(exec_data[-1][7] - exec_data[-1][6])
                order_time = exec_data[-1][5]
                price = exec_data[-1][17]
                # print(side)

                fee_rate = self.fee_rate_taker if side.find('market') != -1 else self.fee_rate
                if side == 'buy':
                    fee = '{}_{}'.format('%.8f' % (float(amount_filled) * float(fee_rate)), self.market_currency)
                else:
                    fee = '{}_{}'.format('%.8f' % (float(amount_filled) * float(price) * fee_rate), self.base_currency)

                data_store = Util.build_order_store(order_id=order_id, side=side, trade_pair=self.symbol[1:],
                    price=price, amount_filled=amount_filled,time_stamp=order_time, client_order_id=self.gid,
                    platform_name='bitfinex', platform_account_id=self.bitfinex_id, strategy_id=self.strategy_id, fee=fee)
                # print('data_store', data_store)
                self.q_orders.put(data_store)
                if self.isTaker:
                    self.q_taker_order_result.put(data_store)
                self.hist[simple_side][exec_data[-1][0]] = exec_data[-1]

                if len(self.hist[simple_side]) > self.hist_lenth:
                    self.hist[simple_side].popitem(last=False)

                if order_id == self.on_deleting:
                    self.delete_result = exec_data[-1]
                    self.update_flags["delete_result"] = True
                # del self.orders[exec_data[-1][0]]

            # elif status.startswith('PARTIALLY FILLED'):
            #     # print(exec_data)
            #     try:
            #         simple_side = 'buy' if exec_data[-1][7] > 0 else 'sell'
            #         side_l = exec_data[-1][8].lower().split(' ')
            #         side = "{} {}".format(simple_side, side_l[-1])
            #         order_id = exec_data[-1][0]
            #         account_id = exec_data[-1][1]
            #         amount_orig = exec_data[-1][7]
            #         amount_remain = exec_data[-1][6]
            #         amount_filled = abs(exec_data[-1][7] - exec_data[-1][6])
            #         order_time = exec_data[-1][5]
            #         # print(side)
            #
            #         data_store = Util.build_order_store(order_id=order_id, side=side, trade_pair=self.symbol[1:],
            #             price=exec_data[-1][17], amount_filled=amount_filled,time_stamp=order_time, client_order_id=self.gid,
            #             platform_name='bitfinex', platform_account_id=self.bitfinex_id, strategy_id=self.strategy_id)
            #         # print('data_store', data_store)
            #         self.q_orders.put(data_store)
            #         self.hist[simple_side][exec_data[-1][0]] = exec_data[-1]
            #
            #         if len(self.hist[simple_side]) > self.hist_lenth:
            #             self.hist[simple_side].popitem(last=False)
            #
            #         if order_id == self.on_deleting:
            #             self.delete_result = exec_data[-1]
            #             self.update_flags["delete_result"] = True
            #     except Exception as ex:
            #         logger.info("Bitfinex recording PARTIALLY FILLED: %s" % ex)

    # asyncio事件循环
    def update(self, flags):
        '''
        :param flags: {"depth": True, 'trade': False}
        :return:
        '''
        timeout = self.timeout
        self.unset_flags(flags)
        self.register_callbacks()
        start = time.time()

        while True:
            time.sleep(0.001)
            # asyncio.sleep(1)
            if self.check_flags(flags):
                break
            if time.time() - start > timeout:
                raise TimeoutError
        self.remove_callbacks()
        return self

    def buy(self, amount, price=-1):
        s_time = time.time()
        order_result = Util.build_order_result(
            status=True, price=price, side='buy',
            platform_id='bitfinex', trade_pair=self.symbol[1:],
            amount_orig=amount, amount_filled=0
        )
        while True:
            price = round(abs(price), self.price_precision) if price > 0 else None
            amount = round(abs(amount), self.amount_precision)
            message, cid = self.build_message(channel='on', amount=amount, price=price)
            self.loop.call_soon_threadsafe(self.q.put_nowait, message)

            try:
                self.update({'new_order_result': False})
            except TimeoutError:
                with self.cid_lock:
                    self.cid_dict[cid] = False
                send('market: {}, function: {}, timeout'.format(self.name, sys._getframe().f_code.co_name),
                     'market: {}, function: {}, timeout'.format(self.name, sys._getframe().f_code.co_name), 'tjx')
                self.error("Bitfinex buy timeout")
                order_result.update({
                    "status": False,
                    "error_message": Constants.ORDER_RESULT_ERROR['timeout']
                })
                self.q_orders_result.put(order_result)
                self.compute_latency(s_time, 'buy')
                return None
            details = self.new_order_result
            # print('buy details: ', details)
            if isinstance(details, list):
                if details[16]:
                    side = details[8].lower()
                    fee_rate = self.fee_rate_taker if side.find('market') != -1 else self.fee_rate
                    res =  Util.build_order_store(status=True,order_id=details[0], side=side, amount_remain=details[6],
                        amount_orig=details[7], price=details[16], client_order_id=self.bitfinex_id, platform_name='bitfinex',
                        platform_account_id=self.gid, strategy_id=self.strategy_id, fee_rate=fee_rate)
                    self.q_maker.put(res)

                # reset order_result
                order_result = Util.build_order_result(
                    status=True, order_id=details[0], side='buy',
                    trade_pair=self.symbol[1:], type=details[8],
                    amount_remain=details[6],
                    amount_orig=details[7], price=details[16],
                    platform_id='bitfinex'
                )
                self.q_orders_result.put(order_result)
                logger.debug("Bitfinex buy: %s" % order_result)
                self.compute_latency(s_time, 'buy')
                return order_result

            if isinstance(details, dict):
                logger.info('Bitfinex Buy: retry %s' % amount)
                time.sleep(1)
                continue

    def sell(self, amount, price=-1):
        order_result = Util.build_order_result(
            status=True, price=price, side='sell',
            platform_id='bitfinex', trade_pair=self.symbol[1:],
            amount_orig=amount, amount_filled=0
        )
        while True:
            price = round(abs(price), self.price_precision) if price > 0 else None
            amount = round(-abs(amount), self.amount_precision)
            message, cid = self.build_message(channel='on', amount=amount, price=price)
            self.loop.call_soon_threadsafe(self.q.put_nowait, message)

            try:
                self.update({'new_order_result': False})
            except TimeoutError:
                with self.cid_lock:
                    self.cid_dict[cid] = False
                send('market: {}, function: {}, timeout'.format(self.name, sys._getframe().f_code.co_name),
                     'market: {}, function: {}, timeout'.format(self.name, sys._getframe().f_code.co_name), 'tjx')
                self.error("Bitfinex sell timeout")
                order_result.update({
                    "status": False,
                    "error_message": Constants.ORDER_RESULT_ERROR['timeout']
                })
                self.q_orders_result.put(order_result)
                return None
            details = self.new_order_result
            # print('sell details: ', details)
            if isinstance(details, list):
                if details[16]:
                    side = details[8].lower()
                    fee_rate = self.fee_rate_taker if side.find('market') != -1 else self.fee_rate
                    res = Util.build_order_store(status=True, order_id=details[0], side=side, amount_remain=details[6],
                        amount_orig=details[7], price=details[16], client_order_id=self.bitfinex_id, platform_name='bitfinex',
                        platform_account_id=self.gid, strategy_id=self.strategy_id, fee_rate=fee_rate)
                    self.q_maker.put(res)
                # reset order_result
                order_result = Util.build_order_result(status=True, order_id=details[0],
                                                       side='sell',trade_pair=self.symbol[1:],
                                                       amount_remain=details[6], amount_orig=details[7],
                                                       price=details[16], platform_id='bitfinex')
                self.q_orders_result.put(order_result)
                logger.debug("Bitfinex sell: %s" % order_result)
                return order_result
            if isinstance(details, dict):
                logger.info('Bitfinex Sell: retry %s' % amount)
                time.sleep(1)
                continue

    def deleteOrder(self, order_id):
        s_time = time.time()
        while True:
            message = self.build_message(channel='oc', order_id=order_id)
            self.loop.call_soon_threadsafe(self.q.put_nowait, message)
            self.on_deleting = order_id
            try:
                self.update({'delete_result': False})
            except TimeoutError:
                self.error("Bitfinex deleteOrder timeout, Retry")
                continue
            self.on_deleting = None
            details = self.delete_result
            if details[1] != 'oc-req':
                ret = Util.build_order_result(status=True, order_id=details[0], amount_remain=details[6], amount_orig=details[7])
            else:
                ret = Util.build_order_result(status=False, order_id=details[4][0])
            logger.debug("Bitfinex deleteOrder: %s" % ret)
            # 将删除订单的结果入库
            ret['platform_id'] = 'bitfinex'
            self.q_cancelled_orders.put(ret)
            self.compute_latency(s_time, 'cancel')
            return ret

    def getOrder(self, order_id):
        # print(self.orders, order_id)
        try:
            if order_id in self.orders:
                # return self.orders[order_id]

                detail = self.orders[order_id]
                amount_remain = detail[6]
                amount_orig = detail[7]
                price = detail[16]
                side = 'buy' if amount_orig > 0 else 'sell'
                amount_filled_this_time = detail[-1]
                order_time = detail[2]
                return Util.build_order_result(order_id=order_id, side=side,trade_pair=self.symbol,price=price, amount_remain=amount_remain, amount_filled_this_time=amount_filled_this_time,amount_orig=amount_orig,time_stamp=order_time, status=True)

            else:
                # return None
                return Util.build_order_result(status=False)
        except Exception as ex:
            self.error("Bitfinex getOrder: %s" % ex)

    def request(self, resource, params, type):
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
        }
        if type == "post":
            temp_params = urllib.parse.urlencode(params)
            res = self.session.post(url=self.base_url + resource, data=temp_params, timeout=self.timeout, headers=headers)
        elif type == "get":
            res = self.session.get(url='https://api.bitfinex.com' + resource, params=params, timeout=self.timeout)
        if res.status_code == 200:
            return json.loads(res.content, encoding='utf-8')
        else:
            # print(res)
            logger.exception("request error")

    def getAllOrders(self):
        ret = []
        for order_id, details in self.orders:
            detail = self.orders[order_id]
            amount_remain = detail[6]
            amount_orig = detail[7]
            price = detail[16]
            side = 'buy' if amount_orig > 0 else 'sell'
            order_time = detail[2]
            amount_filled_this_time = detail[-1]
            order_result = Util.build_order_result(order_id=order_id, side=side, trade_pair=self.symbol, price=price,
                                           amount_filled_this_time=amount_filled_this_time,
                                           amount_orig=amount_orig, amount_remain=amount_remain, time_stamp=order_time,
                                           status=True)
            ret.append(order_result)
        return ret
        # return self.orders

    def getHist(self, order_id=None, side=None):
        if order_id and side:
            if order_id in self.hist[side]:
                detail = self.hist[side][order_id]
                amount_remain = detail[6]
                amount_orig = detail[7]
                price = detail[16]
                side = 'buy' if amount_orig > 0 else 'sell'
                order_time = detail[2]
                amount_filled_this_time = detail[-1]
                return Util.build_order_result(order_id=order_id, side=side, trade_pair=self.symbol,price=price,
                                                       amount_filled_this_time=amount_filled_this_time,
                                                       amount_orig=amount_orig, amount_remain=amount_remain,
                                                       time_stamp=order_time,
                                                       status=True)
                # return {order_id: self.hist[side][order_id]}
            else:
                return Util.build_order_result(status=False)
                # return {order_id: None}
        # 全体返回未作处理
        return self.hist

    async def send(self):
        # 等待登录
        await asyncio.sleep(5)
        while True:
            message = None
            try:
                if self.websocket and self.websocket.open:
                    message = await self.q.get()
                    await self.websocket.send(message)
                else:
                    await asyncio.sleep(5)
            except websockets.ConnectionClosed as ex:
                self.error('Bitfinex send ConnectionClosed: %s' % ex)
                if message:
                    self.loop.call_soon_threadsafe(self.q.put_nowait, message)
                await self.keep_connect()
                await asyncio.sleep(5)
                continue
            except Exception as ex:
                self.error('Bitfinex send unhandled error: %s' % ex)

    def build_message(self, channel, **kwargs):
        message = ''
        if channel is 'on':
            cid = Util.bfx_get_cid()
            with self.cid_lock:
                self.cid_dict.update({cid: True})
            price = kwargs.get('price', None)
            amount = kwargs.get('amount', None)
            if price:
                _type = 'EXCHANGE LIMIT'
            else:
                _type = 'EXCHANGE MARKET'
            message = [0, 'on', None, {'gid': self.gid, 'cid': cid, 'type': _type, 'symbol': self.symbol, 'amount': str(amount), 'price': str(price),'hidden': 0}]
            return json.dumps(message), cid
        elif channel is 'oc':
            order_id = kwargs.get('order_id')
            message = [0, "oc", None, {"id": order_id}]
            return json.dumps(message)


    async def ws_handler(self):
        '''
        handle task in backthread
        :return:
        '''
        while True:
            channel = None
            try:
                data = await asyncio.wait_for(self.websocket.recv(), timeout=20)
            except asyncio.TimeoutError:
                # No data in 20 seconds, check the connection.
                try:
                    pong_waiter = await self.websocket.ping()
                    await asyncio.wait_for(pong_waiter, timeout=10)
                except asyncio.TimeoutError:
                    # No response to ping in 10 seconds, disconnect.
                    self.error('Bitfinex ws_handler: receive time out')
                    self.depth = {}
                    break
            except Exception as ex:
                try:
                    self.error('Bitfinex ws_handler: %s' % ex)
                    await self.keep_connect()
                    # await asyncio.sleep(5)
                    pong_waiter = await self.websocket.ping()
                    await asyncio.wait_for(pong_waiter, timeout=10)
                except asyncio.TimeoutError:
                    # No response to ping in 10 seconds, disconnect.
                    self.depth = {}
                    break
                except Exception:
                    self.depth = {}
                    break
            else:
                data = json.loads(data)
                # print(data)
                # get channel and dispatch
                if isinstance(data, dict) and data['event'] == 'subscribed':
                    channel = data["channel"]
                elif isinstance(data, list) and data[1] != 'hb':
                    if data[0] == 0:
                        # print(data)
                        channel = data[1]
                    else:
                        channel = data[0]
                if channel in self.methods:
                    await self.methods[channel](data)
                else:
                    pass

    def parse_meta(self, meta_code):
        meta_table = {"eth_usd": ("ETH", "USD", "tETHUSD"),
                      "btc_usd": ("BTC", "USD", "tBTCUSD"),
                      "eth_usdt": ("ETH", "USD", "tETHUSD"),
                      "btc_usdt": ("BTC", "USD", "tBTCUSD"),
                      "eth_btc": ("ETH", "BTC", "tETHBTC"),
                      'eos_eth': ('EOS', 'ETH', 'tEOSETH'),
                      'bch_eth': ('BCH', 'ETH', 'tBCHETH'),
                      'eos_btc': ('EOS', 'BTC', 'tEOSBTC'),
                      'bch_btc': ('BCH', 'BTC', 'tBCHBTC'),
                      }
        return meta_table[meta_code]

    def run(self):
        asyncio.set_event_loop(self.loop)
        while True:
            try:
                self.loop.run_until_complete(self.keep_connect())
                # self.loop.run_until_complete(self.ws_init())
                tasks = [self.ws_handler(), self.send()]
                self.loop.run_until_complete(asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED))
                time.sleep(1)
            except Exception as ex:
                self.error(ex)


if __name__ == '__main__':
    os.environ[Constants.DQUANT_ENV] = "dev"
    loop = asyncio.get_event_loop()
    bf = BitfinexSpotWs('bch_eth', loop)
    #bf.setDaemon(True)
    bf.start()
    time.sleep(10)

    print(bf.sell(amount=0.5, price=1.858))
    time.sleep(100)

    # while True:
    #     #print(bf.buy(amount=0.02))
    #     print(bf.getDepth())
    #     time.sleep(0.5)
    # while True:
    #     print(bf.getOrder(result['order_id']))
    #     time.sleep(2)
    #
    #
    # bf.join()
