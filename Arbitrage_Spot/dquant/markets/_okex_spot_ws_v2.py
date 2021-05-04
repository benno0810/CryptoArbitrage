import os
import sys
import threading
from copy import copy, deepcopy

import websockets
sys.path.append('../../')
import asyncio, collections
import json, time
import logging
import hashlib
import queue
from asyncio import AbstractEventLoop
from dquant.config import cfg
from dquant.constants import Constants
from dquant.markets.market import Market
from dquant.util import Util
from dquant.common.mongo_conn import MongoConnOrder
#from dquant.common.mongo_conn import MongoConn as MongoConnOrder
from dquant.common.email_send import send
from dquant.strategy.trigger import DepthIndexTrigger

logger = logging.getLogger(__name__)


class OkexSpotWs(Market):
    def __init__(self, meta_code,loop):
        self.contract_type = None
        self.symbol = None
        market_currency, base_currency, symbol = self.parse_meta(meta_code)
        super().__init__(market_currency, base_currency, meta_code, cfg.get_float_config(Constants.OKEX_FEE))
        self.apikey = cfg.get_config(Constants.OKEX_APIKEY)
        self.apisec = cfg.get_config(Constants.OKEX_APISEC)
        self.okex_id = cfg.get_config(Constants.OKEX_ID)
        self.strategy_id = cfg.get_config(Constants.OKEX_STRATEGY_ID)
        self.fee_rate_taker = cfg.get_float_config(Constants.OKEX_FEE_TAKER)
        self.base_url = Constants.OKEX_SPOT_WS_BASE
        self.timeout = Constants.OK_HTTP_TIMEOUT
        self.name = 'OKEX'
        self.symbol = symbol
        [self.minimum_amount, self.price_precision, self.amount_precision] = cfg.get_precisions(self.name, market_currency+base_currency)
        if not (self.price_precision and self.amount_precision):
            self.minimum_amount = cfg.get_float_config(Constants.OKEX_MINIMUM_AMOUNT)
            self.amount_precision = cfg.get_int_config(Constants.OKEX_AMOUNT_PRECISION)
            self.price_precision = cfg.get_int_config(Constants.OKEX_PRICE_PRECISION)
        self.depth_channel = "ok_sub_spot_{}_depth_20".format(self.symbol)
        self.sub_trade_channel = "ok_sub_spot_{}_order".format(self.symbol)
        self.q = asyncio.Queue()
        self.order_result_required = False
        self.order = None
        self.q_order_result = queue.Queue()
        self.websocket = None
        self.depth = {'asks':{}, 'bids':{}}
        self.account = {}
        self.hist = {'buy': collections.OrderedDict(), 'sell': collections.OrderedDict()}
        self.hist_lenth = 10
        self.trade = None
        self.delete_order_result = None
        self.active_order = {}
        self.update_flags = {"depth": False}
        self.loop = loop # type: AbstractEventLoop
        self.static_methods_register()
        self.side_map = {'buy':'buy', 'buy_market':'buy', 'sell':'sell', 'sell_market':'sell'}
        self.trade_data_chache = collections.OrderedDict()
        self.trade_data_lock = threading.Lock()
        self.latency_col = MongoConnOrder().client.latency.api_latency
        self.trigger = False
        # self.q_trigger = queue.Queue()

    async def ping(self):
        while True:
            try:
                if self.websocket and self.websocket.open:
                    ping = str({'event': 'ping'})
                    await self.websocket.send(ping)
                    await asyncio.sleep(20)
            except Exception as ex:
                self.error('OKEX ping: %s' % ex)


    async def sub_channel(self):
        login_param = {"api_key":self.apikey}
        login_param['sign'] = self.buildMySign(login_param)
        message = [str({'event': 'addChannel', 'channel': self.depth_channel})]
        message.append(str({"event":"login", "parameters": login_param}))
        for m in message:
            await self.websocket.send(m)

    # 格式化ws传回数据
    def okex_depth_format(self, res, flag):
        result_list = []
        for ticker in res[flag]: result_list.append({
                'price': float(ticker[0]),
                'amount': float(ticker[1])
            })

        if flag == "asks":  # 卖单从小到大
            result_list.sort(key=lambda x: x['price'])
        else:  # 买单从大到小
            result_list.sort(key=lambda x: x['price'], reverse=True)
        return result_list

    def static_methods_register(self):
        self.methods[self.depth_channel] = self.update_depth
        self.methods[self.sub_trade_channel] = self.update_sub_trades

    def register_callbacks(self):
        self.methods[self.depth_channel] = self.update_depth
        self.methods[Constants.OKEX_SPOT_TRADE_WS] = self.update_trade
        self.methods[Constants.OKEX_SPOT_DELETE_ORDER_WS] = self.update_delete_order
        self.methods[Constants.OKEX_SPOT_GET_ORDER_WS] = self.update_get_order
        self.methods[Constants.OKEX_SPOT_USERINFO_WS] = self.update_get_account

    def remove_callbacks(self):
        pass
        # del self.methods[self.depth_channel]
        # del self.methods[Constants.OKEX_SPOT_TRADE_WS]
        # del self.methods[Constants.OKEX_SPOT_DELETE_ORDER_WS]
        # del self.methods[Constants.OKEX_SPOT_GET_ORDER_WS]
        # del self.methods[Constants.OKEX_SPOT_USERINFO_WS]

    async def update_depth(self, depth_data):

        #latency_data =  deepcopy(depth_data)
        #lat = int(time.time()*1000) - latency_data[0]['data']['timestamp']
        #self.latency_col.insert({'timestamp': int(time.time()*1000), 'lantency': lat, 'api': 'depth',
        #                 'market': self.name, 'symbol': self.symbol, 'ip': self.ip})

        list_of_ask = self.okex_depth_format(depth_data[0]["data"], "asks")
        list_of_bid = self.okex_depth_format(depth_data[0]["data"], "bids")
        if self.trigger:
            DepthIndexTrigger.Q_TRIGGER.put({"asks": list_of_ask, 'bids': list_of_bid, "name":self.name})
        self.depth = {"asks": list_of_ask, 'bids': list_of_bid}
        self.update_flags["depth"] = True

    def updata_sub_trades_chache(self, order_id, data):
        with self.trade_data_lock:
            self.trade_data_chache.update({order_id: data})
            if len(self.trade_data_chache) >= 100:
                self.trade_data_chache.popitem(last=False)

    async def update_sub_trades(self, sub_trade_data):
        # self.sync_update_sub_trades(sub_trade_data)
        pass

    def sync_update_sub_trades(self, sub_trade_data):
        '''
        这个函数在v2版本不调用。
        '''

        logger.debug('OKEX sub_trade_data: %s' % sub_trade_data)
        data = sub_trade_data[0]['data']
        order_status = data['status']
        order_id = data['orderId']

        # 缓存tradedata，防止传回数据乱序的情况
        if order_status == 2 and order_id not in self.active_order:
            self.updata_sub_trades_chache(order_id, sub_trade_data)

        side = self.side_map[data['tradeType']]
        if order_status == 0:
            return
        if order_status == 2 and data['tradeType'] == 'buy_market':
            amount_orig = float(data['completedTradeAmount'])
            amount_filled = float(data['completedTradeAmount'])
            price = float(data['averagePrice']) or float(data['tradePrice']) or float(data['tradeUnitPrice'])
        else:
            amount_orig = float(data['tradeAmount'])
            amount_filled = float(data['completedTradeAmount'])
            price = float(data['averagePrice']) or float(data['tradePrice']) or float(data['tradeUnitPrice'])

        if order_status in [1, 2] and order_id in self.active_order:
            hist_amount_filled = 0
            amount_filled_this_time = None
            if order_id in self.hist[side]:
                hist_order = self.hist[side][order_id]
                hist_amount_filled = hist_order['amount_filled']
            if hist_amount_filled:
                if amount_filled <= hist_amount_filled:
                    return
                amount_filled_this_time = amount_filled - hist_amount_filled
            else:
                amount_filled_this_time = amount_filled
            if not amount_filled_this_time:
                return 
            q_message = Util.build_order_result(status=True, order_id=order_id, side=side, amount_orig=amount_orig,  amount_filled=amount_filled, amount_filled_this_time=amount_filled_this_time, trade_pair=self.symbol, price=price, time_stamp=int(time.time() * 1000))
            # logger.debug("q_message:%s" % q_message)
            # print("q_message:", q_message)
            if self.order_result_required:
                logger.debug('OKEXSpot q_order_result: %s' % q_message)
                self.q_order_result.put(q_message)
            self.hist[side][order_id] = q_message
            if len(self.hist[side]) > self.hist_lenth:
                self.hist[side].popitem(last=False)

        fee_rate = self.fee_rate_taker if data['tradeType'].find('market') != -1 else self.fee_rate
        if order_status == 2 and order_id in self.active_order:
            self.order_result = Util.build_order_store(order_id=order_id, side=data['tradeType'],
                amount_filled=amount_filled, trade_pair=self.symbol, price=price, time_stamp=int(time.time() * 1000),
                client_order_id=0, platform_name='okex_spot', platform_account_id=self.okex_id,
                strategy_id=self.strategy_id, fee_rate=fee_rate)
            self.q_orders.put(self.order_result)
            if self.isTaker:
                self.q_taker_order_result.put(self.order_result)

            self._remove_from_active_order(order_id)

        if order_status == -1 and order_id in self.active_order:
            if amount_filled:
                self.order_result = Util.build_order_store(order_id=order_id, side=data['tradeType'],
                    amount_filled=amount_filled, trade_pair=self.symbol,price=price, time_stamp=int(time.time() * 1000),
                    client_order_id=0, platform_name='okex_spot',platform_account_id=self.okex_id,
                    strategy_id=self.strategy_id, fee_rate=fee_rate)
                self.q_orders.put(self.order_result)
            self._remove_from_active_order(order_id)


    async def update_trade(self, trade_data):
        '''
        :param trade_data: [{'data': {'result': True, 'order_id': 14420556515}, 'channel': 'ok_futuresusd_trade'}]
        :return: {'result': True, 'order_id': 14420556515}
        '''
        try:
            # print('trade_data', trade_data, self.active_order)
            if 'error_code' in trade_data[0]["data"]:
                if trade_data[0]["data"]['error_code'] != 20015:    #   订单已成交
                    self.error('OKEX update_trade error %s' %(trade_data[0]["data"]['error_code']))
                self.trade = trade_data[0]["data"]

            elif 'result' in trade_data[0]["data"] and trade_data[0]["data"]['result'] is True:
                # assert trade_data[0]["data"]['result'] == True
                self.trade = trade_data[0]["data"]
        except Exception as ex:
            self.error('update trade error: %s' % ex)
        finally:
            if not self.trade:
                logger.debug("OKEX empty self.trade: %s" % trade_data)
            else:
                self.update_flags['trade'] = True

    async def update_delete_order(self, trade_data):
        '''
        :param trade_data: [{'data': {'result': True, 'order_id': 14420556515}, 'channel': 'ok_futuresusd_trade'}]
        :return: {'result': True, 'order_id': 14420556515}
        '''
        try:
            # print('trade_data', trade_data, self.active_order)
            if 'error_code' in trade_data[0]["data"]:
                if trade_data[0]["data"]['error_code'] != 20015:    #   订单已成交
                    self.error('OKEX update_delete_order error %s' %(trade_data[0]["data"]['error_code']))
                self.delete_order_result = trade_data[0]["data"]

            elif 'result' in trade_data[0]["data"] and trade_data[0]["data"]['result'] is True:
                # assert trade_data[0]["data"]['result'] == True
                self.delete_order_result = trade_data[0]["data"]
        except Exception as ex:
            self.error('update update_delete_order error: %s' % ex)
        finally:
            self.update_flags['delete_order'] = True

    async def update_get_order(self, order_data):
        '''
        :param order_data: [{'data': {'result': True, 'orders': [{'symbol': 'eth_usd', 'lever_rate': 10.0, 'amount': 1.0, 'fee': 0.0, 'contract_name': 'ETH1201', 'unit_amount': 10.0, 'type': 2, 'price_avg': 0.0, 'deal_amount': 0.0, 'price': 450.0, 'create_date': 1512029722000, 'order_id': 14495541683, 'status': -1}]}, 'channel': 'ok_futureusd_orderinfo'}]
        :return: {'result': True, 'orders': [{'symbol': 'eth_usd', 'lever_rate': 10.0, 'amount': 1.0, 'fee': 0.0, 'contract_name': 'ETH1201', 'unit_amount': 10.0, 'type': 2, 'price_avg': 0.0, 'deal_amount': 0.0, 'price': 450.0, 'create_date': 1512029722000, 'order_id': 14495541683, 'status': -1}]}
        '''
        # logger.debug("update_get_order: %s" % order_data)
        self.order = order_data[0]["data"]

        self.update_flags['get_order'] = True

    async def update_get_account(self, account_data):
        '''
        :param account_data: [{'data': {'result': True, 'info': {'btc': {'balance': 0.0, 'rights': 0.0, 'contracts': []}, 'etc': {'balance': 0.0, 'rights': 0.0, 'contracts': []}, 'bch': {'balance': 0.0, 'rights': 0.0, 'contracts': []}, 'eth': {'balance': 0.10016739, 'rights': 0.10016739, 'contracts': [{'contract_type': 'this_week', 'freeze': 0.0, 'balance': 5.058e-05, 'contract_id': 20171208260, 'available': 0.10016739, 'profit': -5.058e-05, 'bond': 0.0, 'unprofit': 0.0}]}, 'ltc': {'balance': 0.0, 'rights': 0.0, 'contracts': []}}}, 'channel': 'ok_futureusd_userinfo'}]
        :return:
        '''
        if 'result' in account_data[0]["data"] and account_data[0]["data"]['result'] is True:
            # 仅包含可用余额，不包括冻结余额
            self.account = account_data[0]["data"]['info']['funds']['free']
        self.update_flags['get_account'] = True

    def update(self, flags):
        '''
        :param flags: {"depth": True, 'trade': False}
        :return:
        '''
        self.unset_flags(flags)
        self.register_callbacks()
        timeout = self.timeout
        start = time.time()

        while True:
            time.sleep(0.001)
            if self.check_flags(flags):
                break
            if time.time() - start > timeout:
                raise TimeoutError
        self.remove_callbacks()
        return self

    def buy(self, price, amount=-1):
        '''
        :param price:BTC :最少买入0.01个BTC 的金额(金额>0.01*卖一价) / LTC :最少买入0.1个LTC 的金额(金额>0.1*卖一价) / ETH :最少买入0.01个ETH 的金额(金额>0.01*卖一价)
        :param amount: 市价买单不传amount.BTC 数量大于等于0.01 / LTC 数量大于等于0.1 / ETH 数量大于等于0.01
        :return: {"result": true,"order_id": 6189}
        '''
        s_time = time.time()
        type = ''
        if amount > 0:
            type = 'buy'
            price = round(abs(float(price)), self.price_precision)
            amount = round(abs(float(amount)), self.amount_precision)
            message = self.build_message(price=price, amount=amount, type=type, channel=Constants.OKEX_SPOT_TRADE_WS)
        else:
            type = 'buy_market'
            price = round(abs(float(price)), self.price_precision)
            message = self.build_message(price=price, type=type, channel=Constants.OKEX_SPOT_TRADE_WS)

        # asyncio.Queue is not thread safe
        self.loop.call_soon_threadsafe(self.q.put_nowait, message)

        # default order_result dict
        order_result = Util.build_order_result(
            status=True, trade_pair=self.symbol, platform_id='okex_spot',
            price=price, side='buy'
        )
        try:
            self.update({'trade': False})
        except TimeoutError:
            send('market: {}, function: {}, timeout'.format(self.name, sys._getframe().f_code.co_name), 'market: {}, function: {}, timeout'.format(self.name, sys._getframe().f_code.co_name), 'tjx')
            self.error("OKEX buy timeout")
            order_result.update(dict(
                status=False,
                error_message=Constants.ORDER_RESULT_ERROR['timeout']
            ))
            self.q_orders_result.put(order_result)
            self.compute_latency(s_time, 'buy')
            return None

        if self.trade and 'order_id' in self.trade:
            # self.active_order[self.trade['order_id']] = self.trade
            self.update_order(self.trade['order_id'])

            if amount > 0:
                self.q_maker.put({'price': price, 'type': type, 'order_id': self.trade['order_id'], 'platform_id': 'okex_spot', 'timestamp': int(time.time()*1000), 'strategy_id': self.strategy_id})
        else:
            self.error('OKEX buy: %s, None' % self.trade)
            order_result.update(dict(
                status=False,
                error_message=str(self.trade)
            ))
            self.q_orders_result.put(order_result)
            self.compute_latency(s_time, 'buy')
            return None
        logger.debug("OKEXSpot buy: %s" % self.trade)

        ret = self.trade
        error_message = 'buy fail' if ret['result'] is False else ''
        self.trade = None
        order_result.update(dict(
            status=ret['result'],
            order_id=ret['order_id'],
            error_message=error_message
        ))
        self.q_orders_result.put(order_result)
        self.compute_latency(s_time, 'buy')
        return ret

    def sell(self, amount, price=-1):
        '''
        :param amount:市价卖单不传price
        :param price:
        :return:{"result": true,"order_id": 6189}
        '''
        if price > 0:
            type = 'sell'
            price = round(abs(float(price)), self.price_precision)
            amount = round(abs(float(amount)), self.amount_precision)
            message = self.build_message(price=price, amount=amount, type=type, channel=Constants.OKEX_SPOT_TRADE_WS)
        else:
            type = 'sell_market'
            amount = round(abs(float(amount)), self.amount_precision)
            message = self.build_message(amount=amount, type=type, channel=Constants.OKEX_SPOT_TRADE_WS)
        self.loop.call_soon_threadsafe(self.q.put_nowait, message)

        order_result = Util.build_order_result(
            status=True, side='sell', trade_pair=self.symbol,
            price=price, platform_id='okex_spot'
        )
        try:
            self.update({'trade': False})
        except TimeoutError:
            send('market: {}, function: {}, timeout'.format(self.name, sys._getframe().f_code.co_name), 'market: {}, function: {}, timeout'.format(self.name, sys._getframe().f_code.co_name), 'tjx')
            self.error("OKEX sell timeout")
            order_result.update(dict(
                status=False,
                error_message=Constants.ORDER_RESULT_ERROR['timeout']
            ))
            self.q_orders_result.put(order_result)
            return None

        if self.trade and 'order_id' in self.trade:
            # self.active_order[self.trade['order_id']] = self.trade
            self.update_order(self.trade['order_id'])
            if price > 0:
                # print('sell result type: ', type)
                self.q_maker.put({'price': price, 'type': type, 'order_id': self.trade['order_id'], 'platform_id': 'okex_spot', 'timestamp': int(time.time()*1000), 'strategy_id': self.strategy_id})
        else:
            logger.error("OKEXSpot sell: %s, None" % self.trade)
            order_result.update(dict(
                status=False,
                error_message=str(self.trade)
            ))
            self.q_orders_result.put(order_result)
            return None
        logger.debug("OKEXSpot sell: %s" % self.trade)

        ret = self.trade
        error_message = 'sell fail' if ret['result'] is False else ""
        self.trade = None
        order_result.update(dict(
            status=False,
            error_message=error_message
        ))
        self.q_orders_result.put(order_result)
        return ret

    def _remove_from_active_order(self,order_id):
        if order_id in self.active_order:
            del self.active_order[order_id]

    def deleteOrder(self, order_id, tillOK=True):
        '''
        :param order_id:
        :return: {'result': True, 'order_id': '14435081666'}
        status(int): 订单状态(0等待成交 1部分成交 2全部成交 -1撤单 3撤单处理中)
        '''
        s_time = time.time()
        result = None
        while True:
            try:
                message = self.build_message(order_id=order_id, channel=Constants.OKEX_SPOT_DELETE_ORDER_WS)
                self.loop.call_soon_threadsafe(self.q.put_nowait, message)
                try:
                    self.update({'delete_order': False})
                except TimeoutError:
                    self.error("OKEX deleteOrder timeout, Retry")
                    continue

                # 多线程调用
                order_details = self.getOrder_api(order_id)
                # order_details = self.update_order(order_id)
                if order_details['status'] and 'order_status' in order_details:
                    order_status = order_details['order_status']
                    if order_status in [2, -1, 3]:
                        # self._remove_from_active_order(order_id)
                        logger.debug("OKEXSpot deleteOrder: %s" % order_details)
                        result = order_details
                        break
                if tillOK:
                    self.error('OKEX delete error: %s' % self.delete_order_result)
                    continue
                else:
                    result = Util.build_order_result(status=False, order_id=order_id)
                    break
                # try:
            except Exception as e:
                logger.exception("message")
                if tillOK:
                    continue
                result = Util.build_order_result(status=False,
                                                 order_id=order_id)
                break
        # 存储数据
        result['platform_id'] = 'okex_spot'
        self.q_cancelled_orders.put(result)
        self.compute_latency(s_time, 'cancel')
        return result

    def getOrder(self, order_id):
        if order_id in self.active_order:
            return self.active_order[order_id]
        else:
            return Util.build_order_result(status=False, order_id=order_id)

    def updateOrderInfoThread(self, update_order_info_event, seconds):
        '''
        every 1 sec update dep
        :param update_depth_event:
        :return:
        '''
        self.updateOrderInfoTable()
        if not update_order_info_event.is_set():
            timer_thread = threading.Timer(seconds, self.updateOrderInfoThread, [update_order_info_event,seconds])
            timer_thread.setDaemon(True)
            timer_thread.start()

    def updateOrderInfoTable(self):
        temp_active_order = copy(self.active_order)
        for order_id in temp_active_order:
            if order_id:
                self.update_order(order_id)

    def update_order(self, order_id, tillOK=True):
        '''
        :param order_id:
        :param tillOK:
        :return: {'symbol': 'eth_btc', 'amount': 0.01, 'orders_id': 145918761, 'price': 900.0, 'avg_price': 0, 'create_date': 1514526501000, 'type': 'sell', 'deal_amount': 0, 'order_id': 145918761, 'status': 0}
        '''
        while True:
            try:
                if order_id:
                    message = self.build_message(order_id=order_id, channel=Constants.OKEX_SPOT_GET_ORDER_WS)
                    self.loop.call_soon_threadsafe(self.q.put_nowait, message)
                    try:
                        self.update({'get_order': False})
                    except TimeoutError:
                        self.error('OKEX update_order timeout, retry')
                        continue
                    order = copy(self.order)
                    self.order = None
                    if order and 'result' in order and order['result'] is True:
                        details = order['orders'][0]
                        if details['order_id'] != order_id:
                            continue
                        side = self.side_map[details['type']]
                        amount_filled_this_time = 0
                        price = details['price'] or details['avg_price']
                        order_status = details['status']
                        # print(self.order)
                        if details['type'] == 'buy_market':
                            price = details['avg_price']
                            order_result = Util.build_order_result(status=True, order_id=details['order_id'], side=side,
                                                           amount_orig=details['deal_amount'],
                                                           amount_filled=details['deal_amount'],
                                                           trade_pair=details['symbol'], price=price,
                                                           time_stamp=details['create_date'],
                                                           order_status=order_status
                                                           )
                        else:
                            order_result = Util.build_order_result(status=True, order_id=details['order_id'], side=side, amount_orig=details['amount'],  amount_filled=details['deal_amount'],trade_pair=details['symbol'], price=price, time_stamp=details['create_date'], order_status = order_status)

                        if (order_id not in self.active_order) and (order_id not in self.hist[side]):
                            amount_filled_this_time = order_result['amount_filled']
                            order_result['amount_filled_this_time'] = amount_filled_this_time
                            self.active_order[order_id] = order_result
                        elif order_id in self.active_order:
                            last_order_result = self.active_order[order_id]
                            amount_filled_this_time = order_result['amount_filled'] - last_order_result['amount_filled']
                            order_result['amount_filled_this_time'] = amount_filled_this_time
                            self.active_order[order_id] = order_result

                        # 放入订单列队
                        if amount_filled_this_time and self.order_result_required:
                            logger.debug('OKEXSpot q_order_result: %s' % order_result)
                            self.q_order_result.put(order_result)
                            self.hist[side][order_id] = order_result
                            if len(self.hist[side]) > self.hist_lenth:
                                self.hist[side].popitem(last=False)

                        # 取消订单、完成订单的处理
                        fee_rate = self.fee_rate_taker if details['type'].find('market') != -1 else self.fee_rate

                        if side == 'buy':
                            fee = '{}_{}'.format('%.8f' % (float(details['deal_amount']) * fee_rate), self.market_currency)
                        else:
                            fee = '{}_{}'.format('%.8f' % (float(details['deal_amount']) * float(price) * fee_rate), self.base_currency)

                        if order_status == 2 or (order_status == -1 and details['deal_amount']):
                            q_orders_message = Util.build_order_store(order_id=order_id, side=details['type'],
                                                                       amount_filled=details['deal_amount'],
                                                                       trade_pair=self.symbol, price=price,
                                                                       time_stamp=int(time.time() * 1000),
                                                                       client_order_id=0, platform_name='okex_spot',
                                                                       platform_account_id=self.okex_id,
                                                                       strategy_id=self.strategy_id,
                                                                       fee=fee)
                            self.q_orders.put(q_orders_message)
                            if order_status == 2 and self.isTaker:
                                self.q_taker_order_result.put(q_orders_message)


                        if order_status in [-1, 2]:
                            self._remove_from_active_order(order_id)

                        # print("order_result", order_result)
                        return order_result

                    if tillOK:
                        logger.debug("update_order error, Retry: %s" % (order))
                        continue
                    else:
                        self.error("update_order error: %s" % order)
                        return Util.build_order_result(status=False, order_id=order_id)
                else:
                    return Util.build_order_result(status=False, order_id=order_id)
            except Exception as e:
                self.error("update_order %s" % e)
                if tillOK:
                    continue
                return Util.build_order_result(status=False, order_id=order_id)

    def getOrder_api(self, order_id, tillOK=True):
        '''
        :param order_id:
        :param tillOK:
        :return: {'symbol': 'eth_btc', 'amount': 0.01, 'orders_id': 145918761, 'price': 900.0, 'avg_price': 0, 'create_date': 1514526501000, 'type': 'sell', 'deal_amount': 0, 'order_id': 145918761, 'status': 0}
        '''
        while True:
            try:
                if order_id:
                    message = self.build_message(order_id=order_id, channel=Constants.OKEX_SPOT_GET_ORDER_WS)
                    self.loop.call_soon_threadsafe(self.q.put_nowait, message)
                    try:
                        self.update({'get_order': False})
                    except TimeoutError:
                        self.error('OKEX getOrder_api timeout, retry')
                        continue
                    # print(self.order)
                    order = copy(self.order)
                    self.order = None
                    if order and 'result' in order and order['result'] is True:
                            details = order['orders'][0]
                            if details['order_id'] != order_id:
                                continue
                            side = self.side_map[details['type']]
                            price = details['price'] or details['avg_price']
                            order_status = details['status']
                            # print(self.order)
                            if details['type'] == 'buy_market':
                                price = details['avg_price']
                                return Util.build_order_result(status=True, order_id=details['order_id'], side=side,
                                                               amount_orig=details['deal_amount'],
                                                               amount_filled=details['deal_amount'],
                                                               trade_pair=details['symbol'], price=price,
                                                               time_stamp=details['create_date'],
                                                               order_status=order_status
                                                               )

                            return Util.build_order_result(status=True, order_id=details['order_id'], side=side, amount_orig=details['amount'],  amount_filled=details['deal_amount'],trade_pair=details['symbol'], price=price, time_stamp=details['create_date'], order_status = order_status)
                    if tillOK:
                        continue
                    else:
                        self.error(order)
                        return Util.build_order_result(status=False, order_id=order_id)
                else:
                    return Util.build_order_result(status=False, order_id=order_id)
            except Exception as e:
                logger.exception("message")
                if tillOK:
                    continue
                return Util.build_order_result(status=False, order_id=order_id)

    def getDepth(self):
        s_time = time.time()
        error_c = 0
        while True:
            try:
                self.update({"depth": False})
            except TimeoutError:
                error_c += 1
                self.error('OKEX getDepth timeout, retry')
                if error_c >= 5:
                    raise TimeoutError
                continue
            if self.depth:
                break
            time.sleep(0.5)
        self.compute_latency(s_time, 'depth')
        return self.depth

    def getAccount(self, coin=[]):
        error_c = 0
        while True:
            message = self.build_message(channel=Constants.OKEX_SPOT_USERINFO_WS)
            self.loop.call_soon_threadsafe(self.q.put_nowait, message)
            # 不需要做timeout异常处理
            try:
                self.update({'get_account': False})
            except TimeoutError:
                self.error('OKEX getAccount timeout, retry')
                error_c += 1
                if error_c >= 5:
                    raise TimeoutError
                continue
            try:
                if coin:
                    ret = {}
                    for c in coin:
                        if c.lower() in self.account:
                            ret[c.lower()] = float(self.account[c.lower()])
                        else:
                            ret[c.lower()] = 0.0
                    return ret
                else:
                    return self.account
            except Exception as ex:
                logger.exception("message")
                error_c += 1
                if error_c >= 5:
                    raise TimeoutError

    def getHist(self, order_id=None, side=None):
        if order_id and side:
            if order_id in self.hist[side]:
                return self.hist[side][order_id]
            else:
                return Util.build_order_result(status=False)

    async def send(self):
        # 等待登录
        await asyncio.sleep(1)
        while True:
            message = None
            try:
                if self.websocket and self.websocket.open:
                    message = await self.q.get()
                    await self.websocket.send(message)
                else:
                    await asyncio.sleep(5)
            except websockets.ConnectionClosed as ex:
                self.error('OKEX send ConnectionClosed: %s' % ex)
                if message:
                    self.loop.call_soon_threadsafe(self.q.put_nowait, message)
                # await self.keep_connect()
                await asyncio.sleep(5)
                continue
            except Exception as ex:
                self.error('OKEX send unhandled error: %s' % ex)

    def build_message(self, channel, event='addChannel', **kwargs):
        '''
        :param channel: subscribe channel
        :param event: default 'addChannel'
        :param kwargs: parameters
        :return:
        '''
        params = {}

        # 删除订单/获取订单
        if channel is Constants.OKEX_SPOT_DELETE_ORDER_WS or channel is Constants.OKEX_SPOT_GET_ORDER_WS:
            order_id = kwargs.get('order_id')
            params = {'api_key': self.apikey, 'symbol': self.symbol, 'order_id': order_id}

        # 下单
        elif channel is Constants.OKEX_SPOT_TRADE_WS:
            params = {'api_key': self.apikey, 'symbol': self.symbol, 'type': kwargs.get('type')}
            price = kwargs.get('price', None)
            amount = kwargs.get('amount', None)
            if price:
                params['price'] = str(price)
            if amount:
                params['amount'] = str(amount)

        # 默认参数
        else:
            params = {'api_key': self.apikey}

        params['sign'] = self.buildMySign(params)
        message = str({'event': event, 'channel': channel, 'parameters': params})
        return message

    def buildMySign(self, params):
        sign = ''
        for key in sorted(params.keys()):
            sign += key + '=' + str(params[key]) + '&'
        return hashlib.md5((sign + 'secret_key=' + self.apisec).encode("utf-8")).hexdigest().upper()

    def parse_meta(self, meta_code):
        meta_table = {"btc_usdt": ("btc", "usdt", "btc_usdt"),
                      "eth_btc": ("eth", "btc", "eth_btc"),
                      "eth_usdt": ("eth", "usdt", "eth_usdt"),
                      'eos_eth': ('eos', 'eth', 'eos_eth'),
                      'eos_btc': ('eos', 'btc', 'eos_btc'),
                      'bch_eth': ('bch', 'eth', 'bch_eth'),
                      'bch_btc': ('bch', 'btc', 'bch_btc'),}
        return meta_table[meta_code]

    async def ws_init(self):
        await self.sub_channel()

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
                    self.error('OKEX ws_handler: receive time out')
                    self.depth = {}
                    break
            except Exception as ex:
                try:
                    self.error('OKEX ws_handler: %s' % ex)
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
                if isinstance(data, list):
                    channel = data[0].get("channel", None)
                    if channel in self.methods:
                        if self.methods[channel] != None:
                            await self.methods[channel](data)
                    else:
                        pass

    def run(self):
        asyncio.set_event_loop(self.loop)
        update_order_info_event = threading.Event()
        self.updateOrderInfoThread(update_order_info_event, 1)
        while True:
            try:
                self.loop.run_until_complete(self.keep_connect())
                # self.loop.run_until_complete(self.ws_init())
                tasks = [self.ws_handler(), self.send(), self.ping()]
                self.loop.run_until_complete(asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED))
                time.sleep(5)
            except Exception as ex:
                self.error(ex)


if __name__ == '__main__':
    os.environ[Constants.DQUANT_ENV] = "pro"
    loop = asyncio.get_event_loop()
    ok = OkexSpotWs('eos_eth', loop)
    ok.setDaemon(True)
    ok.start()
    time.sleep(5)

    ok.getDepth()
    #res = ok.deleteOrder(63823866)
    #print(res)
    # print(ok.buy(price=round(0.00091699905, 7)))
    # print(ok.buy(price=round(0.00091699905, 7)))
    # print(ok.buy(price=round(0.00091699905, 7)))
    # print(ok.buy(price=round(0.00091699905, 7)))
    # print(ok.buy(price=round(0.00091699905, 7)))
    # print(ok.buy(price=round(0.00091699905, 7)))
    # print(ok.buy(price=round(0.00091699905, 7)))



    time.sleep(1)
    time.sleep(600)
