import sys

sys.path.append('../')
sys.path.append('../../')
from dquant.util import Util
import os
import asyncio, collections
import json, time
import logging
import hashlib
import queue
from asyncio import AbstractEventLoop
from dquant.config import cfg
from dquant.constants import Constants
from dquant.markets.market import Market
from dquant.strategy.trigger import DepthIndexTrigger
logger = logging.getLogger(__name__)


class OkexFutureWs( Market):
    def __init__(self, meta_code,loop):
        self.contract_type = None
        self.symbol = None
        market_currency, base_currency, symbol, contract_type = self.parse_meta(meta_code)
        super().__init__(market_currency, base_currency, meta_code, cfg.get_float_config(Constants.OKEX_FUTURE_FEE))
        self.apikey = cfg.get_config(Constants.OKEX_FUTURE_APIKEY)
        self.apisec = cfg.get_config(Constants.OKEX_FUTURE_APISEC)
        self.base_url = Constants.OKEX_FUTURE_WS_BASE
        self.okex_id = cfg.get_config(Constants.OKEX_FUTURE_ID)
        self.strategy_id = cfg.get_config(Constants.OKEX_FUTURE_STRATEGY_ID)
        self.fee_rate_taker = cfg.get_float_config(Constants.OKEX_FUTURE_FEE_TAKER)
        self.contract_type = contract_type
        self.symbol = symbol
        self.timeout = Constants.OK_HTTP_TIMEOUT
        self.name = "OKEXFuture"
        self.strategy_id = 0
        self.q = asyncio.Queue()
        self.q_order_result = queue.Queue()
        # self.q_trigger = queue.Queue()
        self.position = {}
        self.websocket = None
        self.depth = None
        self.ticker = None
        self.trades = None
        self.index_price = None
        self.trade = None
        self.hist_lenth = 10
        self.order_type = {1: 'long', 2: 'short', 3: 'close_long', 4: 'close_short'}
        self.unique_active_orders = {}
        # self.order_result_required = False
        # self.q_order_result = queue.Queue()
        self.depth_channel = "ok_sub_future_{}_depth_{}_usd_20".format(self.market_currency, self.contract_type)
        self.ticker_channel = 'ok_sub_futureusd_{}_ticker_{}'.format(self.market_currency, self.contract_type)
        self.trades_channel = 'ok_sub_futureusd_{}_trade_{}'.format(self.market_currency, self.contract_type)
        self.index_price_channel = 'ok_sub_futureusd_{}_index'.format(self.market_currency)
        self.hist={'delete': collections.OrderedDict()}
        for _type_num, _type in self.order_type.items():
            self.hist[_type] = collections.OrderedDict()
        # self.lock = threading.Lock()
        self.update_flags = {"depth": False}
        self.loop = loop # type: AbstractEventLoop
        self.static_methods_register()

    # 订阅频道
    async def sub_channel(self):
        # X值为：btc, ltc
        # sub depth
        # channel = "ok_sub_future_btc_depth_this_week_usd"
        message = [str({'event': 'addChannel', 'channel': self.depth_channel}),
                   self.build_message(channel=Constants.OKEX_FUTURE_LOGIN, event='login'),
                   str({'event': 'addChannel', 'channel': self.ticker_channel}),
                   str({'event': 'addChannel', 'channel': self.trades_channel}),
                   str({'event':'addChannel','channel': self.index_price_channel})
                   ]
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
        self.methods[Constants.OKEX_FUTURE_LOGIN] = self.login
        # 接收订单更新信息
        self.methods[Constants.OKEX_FUTURE_SUB_TRADES] = self.sub_trades
        self.methods[Constants.OKEX_FUTURE_SUB_POSITIONS] = self.sub_position
        self.methods[self.index_price_channel] = self.update_index_price

    def register_callbacks(self):
        self.methods[self.depth_channel] = self.update_depth
        self.methods[self.ticker_channel] = self.update_ticker
        self.methods[self.trades_channel] = self.update_trades
        self.methods[self.index_price_channel] = self.update_index_price
        self.methods[Constants.OKEX_FUTURE_LOGIN] = self.login
        self.methods[Constants.OKEX_FUTURE_TRADE_WS] = self.update_trade
        self.methods[Constants.OKEX_FUTURE_DELETE_ORDER_WS] = self.update_trade
        self.methods[Constants.OKEX_FUTURE_GET_ORDER_WS] = self.update_get_order
        self.methods[Constants.OKEX_FUTURE_USERINFO_WS] = self.update_get_account

    def remove_callbacks(self):
        # del self.methods[self.depth_channel]
        del self.methods[Constants.OKEX_FUTURE_LOGIN]
        del self.methods[Constants.OKEX_FUTURE_TRADE_WS]
        del self.methods[Constants.OKEX_FUTURE_DELETE_ORDER_WS]
        del self.methods[Constants.OKEX_FUTURE_GET_ORDER_WS]
        del self.methods[Constants.OKEX_FUTURE_USERINFO_WS]

    def getDepth(self):
        self.update({"depth": False})
        return self.depth

    def get_ticker(self):
        self.update({'ticker': False})
        return self.ticker

    def get_trades(self):
        self.update({'trades': False})
        return self.trades

    def get_index_price(self):
        self.update({'index_price': False})
        return self.index_price

    async def sub_position(self, data):
        # print(data)
        symbol = data[0]['data']['symbol']
        for side in data[0]['data']['positions']:
            position = self.contract_type[side['position']]
            key = symbol + '_' + position + '_position'
            hold_amount = side['hold_amount']
            self.position[key] = hold_amount

    async def sub_trades(self, sub_trades):
        '''
        :param sub_trades:
        :return: {15411968317: {'lever_rate': 10.0, 'amount': 1.0, 'orderid': 15411968317, 'contract_id': 20171215013, 'fee': 0.0, 'contract_name': 'BTC1215', 'unit_amount': 100.0, 'price_avg': 0.0, 'type': 1, 'deal_amount': 0.0, 'contract_type': 'this_week', 'user_id': 6240992, 'system_type': 0, 'price': 16500.0, 'create_date_str': '2017-12-11 17:02:18', 'create_date': 1512982938351, 'status': 0}, 15411968630: {'lever_rate': 10.0, 'amount': 1.0, 'orderid': 15411968630, 'contract_id': 20171215013, 'fee': 0.0, 'contract_name': 'BTC1215', 'unit_amount': 100.0, 'price_avg': 0.0, 'type': 1, 'deal_amount': 0.0, 'contract_type': 'this_week', 'user_id': 6240992, 'system_type': 0, 'price': 16500.0, 'create_date_str': '2017-12-11 17:02:18', 'create_date': 1512982938625, 'status': 0}}
        '''
        # print('sub_trades', sub_trades)
        # doc 中 orderid 和 order_id都有，实际返回只有orderid
        logger.info("sub_trades: %s" % sub_trades)
        order_id = sub_trades[0]["data"]['orderid']
        price = sub_trades[0]["data"]['price']
        price_avg = sub_trades[0]["data"]['price_avg']
        status = sub_trades[0]["data"]['status']
        amount = sub_trades[0]["data"]['amount']
        deal_amount = sub_trades[0]["data"]['deal_amount']
        trade_pair = sub_trades[0]["data"]['contract_name'] + '_' + sub_trades[0]["data"]['contract_type']
        order_time = sub_trades[0]["data"]['create_date']
        side = self.order_type[sub_trades[0]["data"]['type']]
        # account_id = sub_trades[0]["data"]['user_id']

        # 成交或者部分成交
        if status == 2 or status == 1:
            if order_id in self.unique_active_orders:
                last_amount_filled = self.unique_active_orders[order_id]['amount_filled']
                if deal_amount <= last_amount_filled:
                    return
            message = {'order_id': order_id,
                       'amount_orig': amount,
                       'amount_filled': deal_amount,
                       'message_type': 'order update',
                       'side': side}
            self.unique_active_orders[order_id] = message
            logger.debug("OKEXFuture q_order_result: %s" % message)
            self.q_order_result.put(message)

        # 成交或者撤单成功, 记入历史订单
        if status == 2 or status == -1:
            try:
                if status == 2 or (status == -1 and deal_amount):
                    data_store = Util.build_order_store(order_id=order_id,
                                                        side=side,
                                                        amount_filled=deal_amount,
                                                        time_stamp=order_time,
                                                        trade_pair=trade_pair,
                                                        price=price_avg or price,
                                                        client_order_id=0,
                                                        platform_name='okex_future',
                                                        platform_account_id=self.okex_id,
                                                        strategy_id=self.strategy_id,
                                                        fee_rate=self.fee_rate)
                    self.q_orders.put(data_store)

                if status == -1:
                    side = 'delete'
                else:
                    side = self.order_type[sub_trades[0]["data"]['type']]
                self.hist[side][order_id] = sub_trades[0]["data"]
                if len(self.hist[side]) > self.hist_lenth:
                    self.hist[side].popitem(last=False)
            except Exception as ex:
                logger.error('OKEX Future: sub_trades %s' % ex)

    async def login(self, data):
        if data[0]['data']['result'] is True:
            self.update_flags['login'] = True

    async def update_depth(self, depth_data):
        try:
            list_of_ask = self.okex_depth_format(depth_data[0]["data"], "asks")
            list_of_bid = self.okex_depth_format(depth_data[0]["data"], "bids")
            self.depth = {"asks": list_of_ask, 'bids': list_of_bid}
            # message = {'bid_price': list_of_bid[0]['price'], 'message_type': 'depth update'}
            DepthIndexTrigger.Q_TRIGGER.put({"asks": list_of_ask, 'bids': list_of_bid, "name": self.name})
            self.update_flags["depth"] = True
        except Exception as ex:
            self.error('OKEXFuture update_depth got: %s' % depth_data)

    async def update_ticker(self, ticker_data):
        self.ticker = ticker_data
        self.update_flags['ticker'] = True

    async def update_trades(self, trades_data):
        self.trades = [{'tid': t[0], 'price': t[1], 'amount': t[2], 'time': t[3], 'type': t[4]} for t in trades_data[0]['data']]
        self.update_flags['trades'] = True

    async def update_index_price(self, index_data):
        self.index_price = index_data[0]['data']
        self.index_price["futureIndex"] = float(self.index_price["futureIndex"])
        self.index_price.update({"name": "{}_index".format(self.name)})
        DepthIndexTrigger.Q_TRIGGER.put(self.index_price)
        self.update_flags['index_price'] = True

    async def update_trade(self, trade_data):
        '''
        :param trade_data: [{'data': {'result': True, 'order_id': 14420556515}, 'channel': 'ok_futuresusd_trade'}]
        :return: {'result': True, 'order_id': 14420556515}
        '''
        if trade_data[0]["data"]['result'] is True:
            self.trade = trade_data[0]["data"]
        else:
            if trade_data[0]["data"]['error_code'] != 20015:    # 订单已成交
                logger.error('Order err %s' %(trade_data[0]["data"]['error_code']))
        self.update_flags['trade'] = True

    async def update_get_order(self, order_data):
        '''
        :param order_data: [{'data': {'result': True, 'orders': [{'symbol': 'eth_usd', 'lever_rate': 10.0, 'amount': 1.0, 'fee': 0.0, 'contract_name': 'ETH1201', 'unit_amount': 10.0, 'type': 2, 'price_avg': 0.0, 'deal_amount': 0.0, 'price': 450.0, 'create_date': 1512029722000, 'order_id': 14495541683, 'status': -1}]}, 'channel': 'ok_futureusd_orderinfo'}]
        :return: {'result': True, 'orders': [{'symbol': 'eth_usd', 'lever_rate': 10.0, 'amount': 1.0, 'fee': 0.0, 'contract_name': 'ETH1201', 'unit_amount': 10.0, 'type': 2, 'price_avg': 0.0, 'deal_amount': 0.0, 'price': 450.0, 'create_date': 1512029722000, 'order_id': 14495541683, 'status': -1}]}
        '''
        self.order = order_data[0]["data"]
        self.update_flags['get_order'] = True

    async def update_get_account(self, account_data):
        '''
        :param account_data: [{'data': {'result': True, 'info': {'btc': {'balance': 0.0, 'rights': 0.0, 'contracts': []}, 'etc': {'balance': 0.0, 'rights': 0.0, 'contracts': []}, 'bch': {'balance': 0.0, 'rights': 0.0, 'contracts': []}, 'eth': {'balance': 0.10016739, 'rights': 0.10016739, 'contracts': [{'contract_type': 'this_week', 'freeze': 0.0, 'balance': 5.058e-05, 'contract_id': 20171208260, 'available': 0.10016739, 'profit': -5.058e-05, 'bond': 0.0, 'unprofit': 0.0}]}, 'ltc': {'balance': 0.0, 'rights': 0.0, 'contracts': []}}}, 'channel': 'ok_futureusd_userinfo'}]
        :return:
        '''
        if account_data[0]["data"]['result'] is True:
            self.account = account_data[0]["data"]['info']
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
            if (self.check_flags(flags)):
                break
            if time.time() - start > timeout:
                raise TimeoutError
        self.remove_callbacks()
        return self

    def long(self, amount, price=-1, lever_rate='10'):
        logger.debug("OKEXFuture Long: %s @%s, lever_rate=%s" % (amount, price, lever_rate))
        message = self.build_message(price=price, amount=amount, type='1', lever_rate=lever_rate, channel=Constants.OKEX_FUTURE_TRADE_WS)
        # asyncio.Queue is not thread safe
        self.loop.call_soon_threadsafe(self.q.put_nowait, message)
        self.update({'trade': False})
        logger.debug("OKEXFuture Long Result: %s" % self.trade)
        return self.trade

    def short(self, amount, price=-1, lever_rate='10'):
        logger.debug("OKEXFuture Short: %s @%s, lever_rate=%s" % (amount, price, lever_rate))
        message = self.build_message(price=price, amount=amount, type='2', lever_rate=lever_rate, channel=Constants.OKEX_FUTURE_TRADE_WS)
        self.loop.call_soon_threadsafe(self.q.put_nowait, message)
        self.update({'trade': False})
        logger.debug("OKEXFuture Short Result: %s" % self.trade)
        return self.trade

    def closeLong(self, amount, price=-1):
        logger.debug("OKEXFuture closeLong: %s @%s" % (amount, price))
        message = self.build_message(price=price, amount=amount, type='3', channel=Constants.OKEX_FUTURE_TRADE_WS)
        self.loop.call_soon_threadsafe(self.q.put_nowait, message)
        self.update({'trade': False})
        logger.debug("OKEXFuture closeLong Result: %s" % self.trade)
        return self.trade

    def closeShort(self, amount, price=-1):
        logger.debug("OKEXFuture closeShort: %s @%s" % (amount, price))
        message = self.build_message(price=price, amount=amount, type='4', channel=Constants.OKEX_FUTURE_TRADE_WS)
        self.loop.call_soon_threadsafe(self.q.put_nowait, message)
        self.update({'trade': False})
        logger.debug("OKEXFuture closeShort Result: %s" % self.trade)
        return self.trade

    def deleteOrder(self, order_id, tillOK=True):
        '''
        :param order_id:
        :return: {'result': True, 'order_id': '14435081666'}
        status(int): 订单状态(0等待成交 1部分成交 2全部成交 -1撤单 4撤单处理中)
        '''
        logger.debug("OKEXFuture deleteOrder: id %s" % order_id)
        while True:
            try:
                message = self.build_message(order_id=order_id, channel=Constants.OKEX_FUTURE_DELETE_ORDER_WS)
                self.loop.call_soon_threadsafe(self.q.put_nowait, message)
                self.update({'trade': False})
                if tillOK:
                    order = self.getOrder(order_id)
                    logger.debug("OKEXFuture deleteOrder Result: %s" % order)
                    if 'status' in order:
                        status = order['status']
                        # 仍然在待成交状态，继续cancel order
                        if status == 0 or status == 1:
                            logger.error(order)
                            continue
                        else:
                            logger.debug("OKEXFuture deleteOrder Result: %s" % self.trade)
                            return self.trade
            except Exception as e:
                self.error("OKEXFuture deleteOrder %s" % e)
                if tillOK:
                    continue
                return None

    def getOrder(self, order_id=None, tillOK=True):
        '''
        :param order_id:
        :param tillOK:
        :return: {'symbol': 'eth_usd', 'lever_rate': 10.0, 'amount': 1.0, 'fee': 0.0, 'contract_name': 'ETH1201', 'unit_amount': 10.0, 'type': 2, 'price_avg': 0.0, 'deal_amount': 0.0, 'price': 450.0, 'create_date': 1512029722000, 'order_id': 14495541683, 'status': -1}
        :return:{15411968317: {'lever_rate': 10.0, 'amount': 1.0, 'orderid': 15411968317, 'contract_id': 20171215013, 'fee': 0.0, 'contract_name': 'BTC1215', 'unit_amount': 100.0, 'price_avg': 0.0, 'type': 1, 'deal_amount': 0.0, 'contract_type': 'this_week', 'user_id': 6240992, 'system_type': 0, 'price': 16500.0, 'create_date_str': '2017-12-11 17:02:18', 'create_date': 1512982938351, 'status': 0}, 15411968630: {'lever_rate': 10.0, 'amount': 1.0, 'orderid': 15411968630, 'contract_id': 20171215013, 'fee': 0.0, 'contract_name': 'BTC1215', 'unit_amount': 100.0, 'price_avg': 0.0, 'type': 1, 'deal_amount': 0.0, 'contract_type': 'this_week', 'user_id': 6240992, 'system_type': 0, 'price': 16500.0, 'create_date_str': '2017-12-11 17:02:18', 'create_date': 1512982938625, 'status': 0}}
        '''
        if order_id:
            while True:
                try:
                    # message = self.build_message(channel=Constants.OKEX_FUTURE_GET_HIST_WS)
                    message = self.build_message(order_id=order_id, channel=Constants.OKEX_FUTURE_GET_ORDER_WS)
                    self.loop.call_soon_threadsafe(self.q.put_nowait, message)
                    self.update({'get_order': False})
                    order = self.order
                    if 'result' in order:
                        if order['result'] is True:
                            order['orders'][0]['type'] = self.order_type[int(order['orders'][0]['type'])]
                            return order['orders'][0] if order['orders'] else None
                    if tillOK:
                        continue
                    else:
                        logger.error(order)
                        break
                except Exception as e:
                    self.error("OKEXFuture getOrder %s" % e)
                    if tillOK:
                        continue
                    return None
        else:
            message = self.build_message(order_id='-1', status='1', current_page='1', page_length='50', channel=Constants.OKEX_FUTURE_GET_ORDER_WS)
            self.loop.call_soon_threadsafe(self.q.put_nowait, message)
            self.update({'get_order': False})
            active_order = {}
            orders = self.order
            for order in orders["orders"]:
                order_id = order['order_id']
                active_order[order_id] = order
            return active_order

    def getAccount(self, coin=[]):
        message = self.build_message(channel=Constants.OKEX_FUTURE_USERINFO_WS)
        self.loop.call_soon_threadsafe(self.q.put_nowait, message)
        self.update({'get_account': False})
        try:
            if coin:
                ret = {}
                for c in coin:
                    if c.lower() in self.account:
                        ret[c.lower()] = self.account[c.lower()]
                    else:
                        ret[c.lower()] = {'balance': 0.0, 'rights': 0.0, 'contracts': []}
                return ret
            else:
                return self.account
        except Exception as ex:
            self.error("OKEXFuture getAccount %s" % ex)

    async def send(self):
        # 等待登录
        await asyncio.sleep(1)
        while True:
            message = await self.q.get()
            await self.websocket.send(message)

    def getHist(self):
        return self.hist

    def build_message(self, channel, event='addChannel', **kwargs):
        '''
        :param channel: subscribe channel
        :param event: default 'addChannel'
        :param kwargs: parameters
        :return:
        '''
        params = {}

        # 删除订单/获取订单
        if channel is Constants.OKEX_FUTURE_DELETE_ORDER_WS or channel is Constants.OKEX_FUTURE_GET_ORDER_WS:
            order_id = kwargs.get('order_id')
            status = kwargs.get('status', None)
            params = {'api_key': self.apikey, 'symbol': self.symbol, 'contract_type': self.contract_type, 'order_id': order_id}
            if status:
                params['status'] = status
                params['current_page'] = kwargs.get('current_page', None)
                params['page_length'] = kwargs.get('page_length', None)

        # 下单
        elif channel is Constants.OKEX_FUTURE_TRADE_WS:
            params = {'api_key': self.apikey, 'symbol': self.symbol, 'contract_type': self.contract_type,
                      'amount': str(kwargs.get('amount')), 'type': str(kwargs.get('type')), 'match_price': "1",
                      'lever_rate': str(kwargs.get('lever_rate', 10))}
            price = kwargs.get('price', None)
            if price > 0:
                params['match_price'] = "0"
                params['price'] = str(price)

        # 默认参数
        else:
            params = {'api_key': self.apikey}

        params['sign'] = self.buildMySign(params, self.apisec)
        message = str({'event': event, 'channel': channel, 'parameters': params})
        return message

    def buildMySign(self, params, secretKey):
        sign = ''
        for key in sorted(params.keys()):
            sign += key + '=' + str(params[key]) + '&'
        return hashlib.md5((sign + 'secret_key=' + secretKey).encode("utf-8")).hexdigest().upper()

    def parse_meta(self, meta_code):
        meta_table = {
            "btc_usd_this_week": ("btc", "usd", "btc_usd", "this_week"),
            "btc_usd_next_week": ("btc", "usd", "btc_usd", "next_week"),
            "btc_usd_quarter": ("btc", "usd", "btc_usd", "quarter"),
            "eth_usd_this_week": ("eth", "usd", "eth_usd", "this_week"),
            "eth_usd_next_week": ("eth", "usd", "eth_usd", "next_week"),
            "eth_usd_quarter": ("eth", "usd", "eth_usd", "quarter"),
        }
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
                    self.error('ws_handler: receive time out')
                    break
            except Exception as ex:
                try:
                    logger.error('ws_handler: %s' % ex)
                    await self.keep_connect()
                    await asyncio.sleep(5)
                    pong_waiter = await self.websocket.ping()
                    await asyncio.wait_for(pong_waiter, timeout=10)
                except asyncio.TimeoutError:
                    # No response to ping in 10 seconds, disconnect.
                    break
            else:
                data = json.loads(data)
                # print(data)
                channel = data[0].get("channel", None)
                if channel in self.methods:
                    if self.methods[channel] != None:
                        await self.methods[channel](data)
                else:
                    pass


    def run(self):
        asyncio.set_event_loop(self.loop)
        while True:
            try:
                self.loop.run_until_complete(self.keep_connect())
                self.loop.run_until_complete(self.ws_init())
                tasks = [self.ws_handler(), self.send()]
                self.loop.run_until_complete(asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED))
                time.sleep(1)
            except Exception as ex:
                self.error(ex)

def test_btc_usd_this_week():
    os.environ[Constants.DQUANT_ENV] = "dev"
    loop = asyncio.new_event_loop()
    ok = OkexFutureWs("btc_usd_this_week", loop)
    ok.start()
    #print(ok.get_ticker())
    #import pdb; pdb.set_trace()
    #print(ok.get_ticker())
    #print(ok.getDepth())
    print(ok.long(amount=1))
    #print(ok.getAccount())


def test_btc_usd_quarter():
    os.environ[Constants.DQUANT_ENV] = "dev"
    loop = asyncio.new_event_loop()
    ok = OkexFutureWs("btc_usd_quarter", loop)
    ok.start()
    #print(ok.get_ticker())
    print(ok.get_index_price())
    #print(ok.getDepth())
    #print(ok.get_trades())
    #print(ok.getAccount())

if __name__ == "__main__":

    test_btc_usd_quarter()
    #test_btc_usd_this_week()