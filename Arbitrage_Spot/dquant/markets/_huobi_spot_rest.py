import gzip
import queue
import sys
import queue
import copy
import collections

import asyncio

sys.path.append('../../')
import base64
import hmac
import os
import datetime
import logging
import threading
from threading import Timer
import traceback

from dquant.config import cfg
from dquant.constants import Constants
import hashlib
import time
import json
import requests
import urllib.parse
import requests.adapters

from dquant.markets.market import Market
from dquant.util import Util
from dquant.common.mongo_conn import MongoConnTrade

requests.adapters.DEFAULT_RETRIES = 5
delay_time = 0.1

logger = logging.getLogger(__name__)

class HuobiRest(Market):
    def __init__(self, meta_code, loop):
        market_currency, base_currency, symbol = self.parse_meta(meta_code)
        super().__init__(market_currency, base_currency, meta_code, cfg.get_float_config(Constants.HUOBI_FEE))
        self.apikey = cfg.get_config(Constants.HUOBI_APIKEY)
        self.apisec = cfg.get_config(Constants.HUOBI_APISEC)
        self.huobi_id = cfg.get_config(Constants.HUOBI_ID)
        self.strategy_id = cfg.get_config(Constants.HUOBI_STRATEGY_ID)
        self.ip_pid_sid = Util.bfx_get_gid(self.strategy_id)
        self.spot_account_id = cfg.get_config(Constants.HUOBI_SPOT_ID)
        self.fee_rate_taker = cfg.get_float_config(Constants.HUOBI_FEE_TAKER)
        self.symbol = symbol
        self.name = 'HuoBiPro'
        # ['min_amount', 'price', 'amount']
        [self.minimum_amount, self.price_precision, self.amount_precision] = cfg.get_precisions(self.name, market_currency+base_currency)
        if not (self.price_precision and self.amount_precision):
            self.minimum_amount = cfg.get_float_config(Constants.HUOBI_MINIMUM_AMOUNT)
            self.amount_precision = cfg.get_int_config(Constants.HUOBI_AMOUNT_PRECISION)
            self.price_precision = cfg.get_int_config(Constants.HUOBI_PRICE_PRECISION)
        self.base_url_api = Constants.HUOBI_REST_BASE
        self.session = requests.session()
        self.timeout = Constants.OK_HTTP_TIMEOUT
        self.orders = []
        self.order_info_table = {}
        # self.updateDepth()
        self.type_map = {'buy-limit':'buy', 'buy-market':'buy', 'sell-limit':'sell', 'sell-market':'sell'}
        self.order_result_required = False
        self.q_order_result = queue.Queue()
        self.hist = {'buy': collections.OrderedDict(), 'sell': collections.OrderedDict()}
        self.hist_lenth = 10
        self.db = MongoConnTrade().client.get_database('trade_huobi')
        self.collection = self.db.get_collection(self.symbol.lower())
        # ws
        self.loop = loop
        self.websocket = None
        self.base_url = 'wss://api.huobipro.com/ws'
        self.channel_depth = 'market.{}.depth.step0'.format(self.symbol)
        self.q = asyncio.Queue()
        self.depth = {}
        self.active_orders = {}
        self.active_orders_lock = threading.Lock()
        self.sub_id = 'id10'  # "id generate by client" 不知道填什么更好
        self.static_methods_register()
        self.update_error = []

    def getHist(self, order_id=None, side=None):
        if order_id and side:
            if order_id in self.hist[side]:
                return self.hist[side][order_id]
                # return {order_id: self.hist[side][order_id]}
            else:
                return Util.build_order_result(status=False)
                # return {order_id: None}
        # 全体返回未作处理
        return self.hist

    def getAccount(self, coin=[], tillOK=True):
        """
        :param acct_id
        :return:
        """
        while True:
            try:
                if not self.spot_account_id:
                    accounts = self.get_account_info()
                    self.spot_account_id = accounts['data'][0]['id']
                url = "/v1/account/accounts/{0}/balance".format(self.spot_account_id)
                params = {"account-id": self.spot_account_id}
                result = self.api_key_get(params, url)
                if result and result['status'] == 'ok':
                    acount_dict = {}
                    for currency in result['data']['list']:
                        if currency['type'] == 'trade':
                            acount_dict.update({currency['currency']: float(currency['balance'])})
                    if coin:
                        ret = {}
                        for c in coin:
                            if c.lower() in acount_dict:
                                ret[c.lower()] = acount_dict[c.lower()]
                            else:
                                ret[c.lower()] = 0.0
                        return ret
                    return acount_dict
                if tillOK:
                    continue
                return None
            except Exception as ex:
                self.error('getAccount: %s' % ex)
                if tillOK:
                    continue

    def depth_format(self, list):
        ret = []
        for item in list:
            price = float(item[0])
            amount = float(item[1])
            ret.append({'price': price, 'amount': amount})
        return ret

    def getDepth(self):
        s_time = time.time()
        error_c = 0
        while True:
            if self.depth:
                self.compute_latency(s_time, 'depth')
                return self.depth
            else:
                self.error('Huobi getDepth: None, Retry')
                error_c += 1
                if error_c >= 5:
                    raise TimeoutError
            time.sleep(5)

    def updateDepth(self, tillOK=True):
        while True:
            try:
                params = {'symbol': self.symbol, 'type': 'step0'}
                url = self.base_url_api + Constants.HUOBI_DEPTH_REST
                res = self.http_get_request(url, params)
                # print(res)
                if not res or res['status'] != 'ok':
                    self.error('Huobi getDepth: no response or wrong status %s' % res)
                    if tillOK:
                        continue
                bid_list = self.depth_format(res['tick']['bids'])
                ask_list = self.depth_format(res['tick']['asks'])
                self.depth = {'bids': bid_list, 'asks': ask_list}
                return {'bids': bid_list, 'asks': ask_list}
            except Exception as ex:
                self.error("Huobi getDepth error: %s" % ex)
                if tillOK:
                    continue
                return {}

    def buy(self, amount, price=-1):
        '''
        :param amount:注意：市价买单时表示买多少钱，市价卖单时表示卖多少币。市价买单最小单位为1！！！
        :param price:
        :return:{'status': 'ok', 'data': '460910789'}
        '''
        s_time = time.time()
        order_result = Util.build_order_result(
            status=True, side='buy', trade_pair=self.symbol,
            price=price, platform_id='huobi',
            amount_orig=amount, amount_filled=0
        )
        try:
            if price > 0:
                price = str(round(float(price), self.price_precision))
                _type = 'buy-limit'
                amount = str(round(amount, self.amount_precision))

            else:
                price = 0
                _type = 'buy-market'
                # 这里需要用到price_precision 而不是amount。因为代表的是base的数量
                amount = str(round(amount, self.price_precision))
            result = self.send_order(amount=amount, source='api', symbol=self.symbol, _type=_type, price=price)

            if result and result['status'] == 'ok':
                result['order_id'] = int(result['data'])
                # 这里的amount是base的数量。注意！只有在maker的时候是准确的
                with self.active_orders_lock:
                    # reset order_result
                    order_result = Util.build_order_result(
                        status=True, order_id=int(result['data']),
                        side="buy", trade_pair=self.symbol,
                        price=price, amount_filled=0,
                        amount_orig=amount, state='submitted',
                        platform_id='huobi'
                    )
                    self.active_orders[int(result['data'])] = order_result
                logger.debug("Huobi Buy: %s, amount:%s, price: %s" % (result, amount, price))
            else:
                self.error("Huobi buy: %s" % result)
                # update default order_result
                order_result.update({
                    "status": False,
                    "error_message": "not response" if not result else str(result)
                })
                self.q_orders_result.put(order_result)
                self.compute_latency(s_time, 'buy')
                return {}

            self.q_orders_result.put(order_result)
            self.compute_latency(s_time, 'buy')
            return result
        except Exception as ex:
            self.error("Huobi buy %s" % ex)
            order_result.update({
                "status": False,
                "error_message": "buy fail, %s" % ex
            })
            self.q_orders_result.put(order_result)
            self.compute_latency(s_time, 'buy')
            return {}

    def sell(self, amount, price=-1):
        '''
        :param amount: 注意：市价买单时表示买多少钱，市价卖单时表示卖多少币。
        :param price:
        :return:
        '''
        # 默认的order result
        order_result = Util.build_order_result(
            status=True, trade_pair=self.symbol, price=price,
            platform_id='huobi', side='sell',
            amount_orig=amount, amount_filled=0
        )
        try:
            if price > 0:
                price = str(round(float(price), self.price_precision))
                _type = 'sell-limit'
            else:
                price = 0
                _type = 'sell-market'
            amount = str(round(amount, self.amount_precision))
            result = self.send_order(amount=amount, source='api', symbol=self.symbol, _type=_type, price=price)

            if result and result['status'] == 'ok':
                result['order_id'] = int(result['data'])
                with self.active_orders_lock:
                    order_result = Util.build_order_result(
                        status=True,
                        order_id=int(result['data']),
                        side="sell", trade_pair=self.symbol,
                        price=price, amount_filled=0,
                        amount_orig=amount, state='submitted',
                        platform_id='huobi'
                    )
                    self.active_orders[int(result['data'])] = order_result
                logger.debug("Huobi Sell: %s, amount:%s, price: %s" % (result, amount, price))
            else:
                self.error("Huobi sell %s" % result)
                order_result.update({
                    "status": False,
                    "error_message": "not response" if not result else str(result)
                })
                self.q_orders_result.put(order_result)
                return {}

            self.q_orders_result.put(order_result)
            return result
        except Exception as ex:
            self.error("Huobi sell %s" % ex)
            order_result.update({
                "status": False,
                "error_message": "sell fail, %s" % ex
            })
            self.q_orders_result.put(order_result)
            return {}

    def send_order(self, amount, source, symbol, _type, price=0):
        """
        :param amount:
        :param source: 如果使用借贷资产交易，请求参数source中填写'margin-api'
        :param symbol:
        :param _type: 可选值 {buy-market：市价买, sell-market：市价卖, buy-limit：限价买, sell-limit：限价卖}
        :param price:
        :return:
        """
        try:

            if not self.spot_account_id:
                # 账户 ID，使用accounts方法获得。币币交易使用‘spot’账户的accountid；借贷资产交易，请使用‘margin’账户的accountid
                accounts = self.get_account_info()
                self.spot_account_id = accounts['data'][0]['id']
        except BaseException as e:
            self.error('get acct_id error.%s' % e)

        params = {"account-id": self.spot_account_id,
                  "amount": amount,
                  "symbol": symbol,
                  "type": _type,
                  "source": source}
        if price:
            params["price"] = price

        result = self.api_key_post(params, Constants.HUOBI_ORDER_REST)

        if result and result['status'] != 'error' and result["data"]:
            if price: # 这里price>0就是limit了(sell & buy里面的逻辑)
                maker_order = Util.build_order_store(order_id=result['data'], side=_type, trade_pair=self.symbol,
                    price=price, client_order_id=self.huobi_id, platform_name='huobi', platform_account_id=self.huobi_id,
                    strategy_id=self.strategy_id)

                self.q_maker.put(maker_order)
            # {'status': 'ok', 'data': '857742463', 'order_id': 857742463}
            self.orders.append(int(result["data"]))  # get orderid and write to obj's array
            # logger.debug("Huobi self.orders: %s" % self.orders)
        return result

    def deleteOrder(self, order_id, tillOK=True):
        '''
        :param orderId:
        :param tillOK:
        :return: {'status': 'ok', 'data': '460960843'}
        '''
        s_time = time.time()
        while True:
            try:
                params = {}
                url = "/v1/order/orders/{0}/submitcancel".format(order_id)
                result = self.api_key_post(params, url)
                logger.debug('Huobi delete: %s' % result)
                # print(result)
                # 3.14更新注释
                # if result['status'] == 'ok':
                #     result = self.simpleGetOrder(order_id)
                #     break

                # 2.28更新注释
                # if not result or result['status'] != 'ok':
                #     self.updateOrderInfo(order_id)

                order_result = self.simpleGetOrder(order_id)
                if 'state' in order_result and order_result['state'] in ['canceled', 'filled', 'partial-canceled']:
                    result = order_result
                    break
                self.error('Huobi Delete Order: %s' % order_result)
                time.sleep(0.5)
                continue
                    # return self.simpleGetOrder(order_id)
            except Exception as ex:
                self.error("Huobi cancel Order %s" % ex)
                if tillOK:
                    continue
        result['platform_id'] = 'huobi'
        self.q_cancelled_orders.put(result)
        self.compute_latency(s_time, 'cancel')
        return result

    def simpleGetOrder(self,order_id, tillOK=True):
        error_c = 0
        result = None
        while True:
            try:
                params = {}
                url = "/v1/order/orders/{0}".format(order_id)
                result = self.api_key_get(params, url)
                # print(result)
                if not result or result['status'] != 'ok':
                    if tillOK:
                        self.error('Huobi getOrder %s, Retry' % result)
                        continue
                    self.error('Huobi getOrder %s' % result)
                data = result['data']
                amount_orig = data.get('amount', '0')
                amount_filled = data.get('field-amount', '0')
                side = self.type_map[data.get('type', '')]
                price = data.get('price', '0')
                state = data.get('state', '')
                if side == 'buy':
                    if data.get('type', '') == 'buy-market':
                        amount_orig = data.get('field-amount', '0')
                        price = float(data.get('field-cash-amount', '0')) / float(amount_filled)
                    order_result = Util.build_order_result(
                        status=True, order_id=data['id'], side=side, trade_pair=data.get('symbol', ''),
                        price=price, amount_filled=amount_filled, amount_orig=amount_orig, state=state)
                else:
                    if data.get('type', '') == 'sell-market':
                        price = float(data.get('field-cash-amount', '0')) / float(amount_filled)
                    amount_filled = data.get('field-amount', '0')
                    order_result = Util.build_order_result(
                        status=True, order_id=data['id'], side=side, trade_pair=data.get('symbol', ''),
                        price=price, amount_filled=amount_filled, amount_orig=amount_orig, state=state)
                return order_result
            except Exception as ex:
                if tillOK:
                    self.error('Huobi getOrder %s, Retry' % result if result else ex)
                    continue
                self.error("Huobi get Order %s" % ex)
                return Util.build_order_result(status=False)
            finally:
                if error_c >= 5:
                    raise TimeoutError


    def updateOrderInfo(self, order_id, tillOK=True):
        '''
        :param order_id:
        :param tillOK:
        :return: {'status': 'ok', 'data': {'id': 460910789, 'symbol': 'ethusdt', 'account-id': 319979, 'amount':
        '0.010000000000000000', 'price': '650.000000000000000000', 'created-at': 1514191861100, 'type': 'buy-limit',
        'field-amount': '0.0', 'field-cash-amount': '0.0', 'field-fees': '0.0', 'finished-at': 0, 'source': 'api', 'state': 'submitted', 'canceled-at': 0}}
        :return(order_id=None): {'status': 'ok', 'data': [{'id': 460910789, 'symbol': 'ethusdt', 'account-id': 319979,
        'amount': '0.010000000000000000', 'price': '650.000000000000000000', 'created-at': 1514191861100, 'type': 'buy-limit',
        'field-amount': '0.0', 'field-cash-amount': '0.0', 'field-fees': '0.0', 'finished-at': 0, 'source': 'api', 'state': 'submitted', 'canceled-at': 0}]}
        {'status': 'ok', 'data': {'id': 529515200, 'symbol': 'ethbtc', 'account-id': 319979, 'amount': '0.010000000000000000', 'price': '0.0', 'created-at': 1514647375183, 'type': 'buy-market', 'field-amount': '0.182000000000000000', 'field-cash-amount': '0.009995986000000000', 'field-fees': '0.000364000000000000', 'finished-at': 1514647375346, 'source': 'api', 'state': 'filled', 'canceled-at': 0}}
        '''
        while True:
            try:
                params = {}
                url = "/v1/order/orders/{0}".format(order_id)
                result = self.api_key_get(params, url)
                # print(result)
                if not result or result['status'] != 'ok':
                    if tillOK:
                        self.error('updateOrderInfo %s, Retry' % result)
                        time.sleep(1)
                        continue
                    self.error('updateOrderInfo %s' % result)

                data = result['data']
                amount_orig = data.get('amount', '0')
                amount_filled = data.get('field-amount', '0')
                side = self.type_map[data.get('type', '')]
                type = data.get('type', '')
                price = data.get('price', '0')

                #fee = data.get('field-fees', '0')
                fee_rate = self.fee_rate

                if side == 'buy':
                    if type == 'buy-market':
                        fee_rate = self.fee_rate_taker
                        amount_orig = data.get('field-amount', '0')
                        price = float(data.get('field-cash-amount', '0')) / float(amount_filled)
                        # price = float(data.get('amount', '0')) / float(amount_filled)
                    order_result = Util.build_order_result(
                        status=True, order_id=data['id'], side=side, trade_pair=data.get('symbol', ''),
                        price=price, amount_filled=amount_filled, amount_orig=amount_orig)
                else:
                    if type == 'sell-market':
                        fee_rate = self.fee_rate_taker
                        price = float(data.get('field-cash-amount', '0')) / float(amount_filled)
                    order_result = Util.build_order_result(
                        status=True, order_id=data['id'], side=side, trade_pair=data.get('symbol', ''),
                        price=price, amount_filled=amount_filled, amount_orig=amount_orig)

                # print(amount_filled, price, fee_rate)
                #print(type(amount_filled), type(price), type(fee_rate))
                if side == 'buy':
                    fee = '{}_{}'.format('%.8f' % (float(amount_filled)*fee_rate), self.market_currency)
                else:
                    fee = '{}_{}'.format('%.8f' % (float(amount_filled)*float(price)*fee_rate), self.base_currency)

                # if amount_orig == amount_filled:
                #     self.hist[side][data['id']] = order_result
                #     self.q_order_result.put(order_result)

                if data['state'] in ['filled', 'partial-canceled']:
                    if data['id'] not in self.hist[side]:
                        if self.order_result_required:
                            logger.debug("Huobi q_order_result: %s" % order_result)
                            self.q_order_result.put(order_result)
                        data_store = Util.build_order_store(order_id=order_id, side=type, trade_pair=self.symbol,
                            price=order_result['price'], amount_filled=float(amount_filled),time_stamp=int(time.time() * 1000),
                            client_order_id=self.huobi_id, platform_name='huobi', platform_account_id=self.huobi_id,
                            strategy_id=self.strategy_id, fee=fee)

                        self.q_orders.put(data_store)
                        if self.isTaker:
                            self.q_taker_order_result.put(data_store)
                        self.hist[side][data['id']] = order_result
                        # 成交或者部分成交取消的订单，放入列队后从orders删除
                        try:
                            self.orders.remove(int(order_id))
                            with self.active_orders_lock:
                                try:
                                    del self.active_orders[int(order_id)]
                                except:
                                    pass
                        except:
                            pass
                    return None
                elif data['state'] == 'canceled':
                    try:
                        self.orders.remove(int(order_id))
                        with self.active_orders_lock:
                            try:
                                del self.active_orders[int(order_id)]
                            except:
                                pass
                    except:
                        pass
                else:
                    with self.active_orders_lock:
                        self.active_orders[data['id']] = order_result
                return order_result

            except Exception as ex:
                self._update_error()
                if self._is_down():
                    self.latency_ok['buy'] = False
                else:
                    self.latency_ok['buy'] = True
                if tillOK:
                    self.error("Huobi UpdateOrderInfo {}, Retry".format(traceback.format_exc()))
                    time.sleep(1)
                    continue
                self.error("Huobi UpdateOrderInfo {}".format(traceback.format_exc()))
                return Util.build_order_result(status=False)

    def _update_error(self):
        ts = time.time()
        self.update_error.append(ts)
        if len(self.update_error) > 5:
            self.update_error.pop(0)

    def _is_down(self):
        if len(self.update_error) >= 3 and self.update_error[-1] - self.update_error[0] <= 180:
            return True
        else:
            return False


    def get_account_info(self):
        """
        :return:{'status': 'ok', 'data': [{'id': 319979, 'type': 'spot', 'subtype': '', 'state': 'working'}]}
        """
        params = {}
        return self.api_key_get(params, Constants.HUOBI_ACCOUNT_BASE)

    def get_trades(self):
        '''
        _id     datetime obj
        tid     "id": 成交id,
        price     "price": 成交价钱,
        amount    "amount": 成交量,
        type     "direction": 主动成交方向,
        timestamp     "ts": 成交时间
                                                                                                                              ''
        output:
            ch
            ts
            data (消息体)
             [
                id:
                ts:
                data: [
                {'id': 17592264311524, 'amount': 0.0656, 'price': 844.96, 'direction': 'buy', 'ts': 1514896297115}
                ] 每个trade
             ]

        根据消息体的id来判断是否重复。每次取50个消息体，里面的order的数量通常多余50个。
        每轮保存下消息体id集合。每轮的每个id判断是否在上次的id集合里，如果不在则入库，否则continue到下一个消息体。
        '''
        msg_ids_last = []

        while True:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36'
            }
            url = self.base_url_api + '/market/history/trade?symbol={}&size={}'.format(self.symbol, 2000)
            rsp = requests.request("GET", url, headers=headers)
            if 'status' in rsp.json() and rsp.json()['status'] == 'error':
                print('res: ', rsp.json(), 'symbol: ', self.symbol)
                continue

            print('rsp: ', rsp.json())
            msg_ids = []
            to_db = []
            for one in rsp.json()['data']:
                #print('one:', one)
                the_id = one['id']
                msg_ids.append(the_id)
                if the_id in msg_ids_last:
                    continue
                for x in one['data']:
                    tmp = {
                        '_id': datetime.datetime.now(),
                        'tid': str(x['id']),
                        'amount': x['amount'],
                        'price': x['price'],
                        'type': x['direction'],
                        'timestamp': x['ts'],
                    }
                    to_db.append(tmp)
                    time.sleep(0.001)

            # print('lens: ', len(to_db))
            if to_db:
                self.collection.insert(to_db)
                # print(len(to_db))
            # 没那么多新trade。睡15min再获取(前几次分别获取到的，eg: 2550->710-785)
            time.sleep(900)
            #print('msg_id2: ', msg_ids)
            msg_ids_last = msg_ids

    def buildMySign(self, params, method, host_url, request_path, secret_key):
        sorted_params = sorted(params.items(), key=lambda d: d[0], reverse=False)
        encode_params = urllib.parse.urlencode(sorted_params)
        payload = [method, host_url, request_path, encode_params]
        payload = '\n'.join(payload)
        payload = payload.encode(encoding='UTF8')
        secret_key = secret_key.encode(encoding='UTF8')

        digest = hmac.new(secret_key, payload, digestmod=hashlib.sha256).digest()
        signature = base64.b64encode(digest)
        signature = signature.decode()
        return signature

    def http_get_request(self, url, params, add_to_headers=None):
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.71 Safari/537.36',
        }
        if add_to_headers:
            headers.update(add_to_headers)
        postdata = urllib.parse.urlencode(params)

        try:
            response = requests.get(url, postdata, headers=headers, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()
        except BaseException as e:
            self.error("httpGet failed, detail is:%s" % e)
        return {}

    def http_post_request(self, url, params, add_to_headers=None):
        headers = {
            "Accept": "application/json",
            'Content-Type': 'application/json'
        }
        if add_to_headers:
            headers.update(add_to_headers)
        postdata = json.dumps(params)

        try:
            response = requests.post(url, postdata, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
        except BaseException as e:
            self.error("httpPost failed, detail is:%s,%s" % (response.text, e))
        return {}

    def api_key_get(self, params, request_path):
        method = 'GET'
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        params.update({'AccessKeyId': self.apikey,
                       'SignatureMethod': 'HmacSHA256',
                       'SignatureVersion': '2',
                       'Timestamp': timestamp})

        host_url = self.base_url_api
        host_name = urllib.parse.urlparse(host_url).hostname
        host_name = host_name.lower()
        params['Signature'] = self.buildMySign(params, method, host_name, request_path, self.apisec)

        url = host_url + request_path
        return self.http_get_request(url, params)

    def api_key_post(self, params, request_path):
        method = 'POST'
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        params_to_sign = {'AccessKeyId': self.apikey,
                          'SignatureMethod': 'HmacSHA256',
                          'SignatureVersion': '2',
                          'Timestamp': timestamp}

        host_url = self.base_url_api
        host_name = urllib.parse.urlparse(host_url).hostname
        host_name = host_name.lower()
        params_to_sign['Signature'] = self.buildMySign(params_to_sign, method, host_name, request_path, self.apisec)
        url = host_url + request_path + '?' + urllib.parse.urlencode(params_to_sign)
        return self.http_post_request(url, params)

    def parse_meta(self, meta_code):
        meta_table = {'eth_usdt': ("eth", "usdt", "ethusdt"),
                      'btc_usdt': ("btc", "usdt", "btcusdt"),
                      'eth_btc': ("eth", "btc", "ethbtc"),
                      'ltc_eth': ('ltc', 'eth', 'ltceth'),
                      'bch_usdt': ('bch', 'usdt', 'bchusdt'),
                      'ven_eth': ('ven', 'eth', 'veneth'),
                      'bch_eth': ('bch', 'eth', 'bcheth'),
                      'bch_btc': ('bch', 'btc', 'bchbtc'),
                      'ltc_btc': ('ltc', 'btc', 'ltcbtc'),
                      'ltc_usdt': ('ltc', 'usdt', 'ltcusdt'),
                      'eos_eth': ('eos', 'eth', 'eoseth'),
                      'eos_btc': ('eos', 'btc', 'eosbtc'),
                      }
        return meta_table[meta_code]

    # def getOrder(self, order_id):
    #     # print(self.order_info_table)
    #     if order_id and order_id in self.order_info_table:
    #         return self.order_info_table[order_id]
    #     return Util.build_order_result(status=False, order_id=order_id)

    def getOrder(self, order_id):
        if order_id and order_id in self.active_orders:
            return self.active_orders[order_id]
        elif order_id:
            return self.simpleGetOrder(order_id)
        else:
            return Util.build_order_result(status=False)

    def get_activate_orders(self, tillOK=True):
        """
        :param symbol:
        :param states: 可选值 {pre-submitted 准备提交, submitted 已提交, partial-filled 部分成交, partial-canceled 部分成交撤销, filled 完全成交, canceled 已撤销}
        :param types: 可选值 {buy-market：市价买, sell-market：市价卖, buy-limit：限价买, sell-limit：限价卖}
        :param start_date:
        :param end_date:
        :param _from:
        :param direct: 可选值{prev 向前，next 向后}
        :param size:
        :return:
        """
        while True:
            params = {'symbol': self.symbol, 'states': 'submitted'}
            result = self.api_key_get(params, Constants.HUOBI_GET_ORDER_REST)
            if (not result or result['status'] != 'ok') and tillOK:
                self.error('getOrder %s' % result)
                continue
            datas = result['data']
            res = []
            for data in datas:
                side = self.type_map[data.get('type', '')]
                tmp = Util.build_order_result(
                    status=True, order_id=data['id'], side=data.get('type', ''), trade_pair=data.get('symbol', ''),
                    price=data.get('price', '0'), amount_filled=data.get('field-amount', '0'),
                    amount_orig=data.get('amount', '0'),
                    amount_remain=float(data.get('amount', '0')) - float(data.get('field-amount', '0')))
                res.append(tmp)
            return res

    def get_our_history_orders(self, tillOK=True):

        while True:
            params = {'symbol': self.symbol, 'states': 'partial-filled,filled'}
            result = self.api_key_get(params, Constants.HUOBI_GET_ORDER_REST)
            if (not result or result['status'] != 'ok') and tillOK:
                self.error('getOrder %s' % result)
                continue
            datas = result['data']
            res = []
            for data in datas:
                #print('data {}'.format(data))
                side = self.type_map[data.get('type', '')]
                tmp = Util.build_order_result(
                    status=True, order_id=data['id'], side=data.get('type', ''), trade_pair=data.get('symbol', ''),
                    price=data.get('price', '0'), amount_filled=data.get('field-amount', '0'),
                    amount_orig=data.get('amount', '0'), time_stamp=data['created-at'],
                    amount_remain=float(data.get('amount', '0')) - float(data.get('field-amount', '0')))
                res.append(tmp)
            return res

    def cancel_active_orders(self, tillOK=True):
        '''
        单次不超过50个订单id
        :param tillOK:
        :return: {'status': 'ok', 'data': {'success': ['562265763'], 'failed': []}}
        '''
        order_ids = [e['order_id'] for e in self.get_activate_orders()]
        lens = len(order_ids)
        print('order_ids: ', order_ids, lens)
        result = {}
        for i in range(0, lens, 50):
            params = {'order-ids': order_ids[i:i+50]}
            result = self.api_key_post(params, Constants.HUOBI_CANCEL_REST)
            if (not result or result['status'] != 'ok') and tillOK:
                continue

        return result

    def updateOrderInfoTable(self):
        temp_orders = copy.deepcopy(self.orders)
        logger.debug("Orders to be update: %s" % self.orders)
        for order_id in temp_orders:
            if order_id:
                order_info = self.updateOrderInfo(order_id)
                if order_info:
                    self.order_info_table[order_id] = order_info
                else:
                    # 已成交
                    self.deleteOrderInfoTable(order_id)

    def deleteOrderInfoTable(self,order_id):
        try:
            del self.order_info_table[order_id]
        except:
            pass

    def getOrderInfo(self,order_id):
        return self.order_info_table[order_id]

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

    def updateDepthThread(self, update_depth_event, seconds):
        '''
        every 1 sec update dep
        :param update_depth_event:
        :return:
        '''
        self.updateDepth()
        if not update_depth_event.is_set():
            timer_thread = threading.Timer(seconds, self.updateDepthThread, [update_depth_event,seconds])
            timer_thread.setDaemon(True)
            timer_thread.start()

    def static_methods_register(self):
        self.methods[self.channel_depth] = self.update_depth

    async def sub_channel(self):
        '''初始已经订阅了kline, depth, trade_detail'''
        message_depth = json.dumps({'id': self.sub_id, 'sub': self.channel_depth})
        await self.websocket.send(message_depth)

    def register_callbacks(self):
        self.methods[self.channel_depth] = self.update_depth

    def huobi_depth_format(self, res, flag):
        result_list = []
        for ticker in res[flag]: result_list.append({
                'price': float(ticker[0]),
                'amount': float(ticker[1])
            })
        if flag == "asks":
            result_list.sort(key=lambda x: x['price'])
        else:
            result_list.sort(key=lambda x: x['price'], reverse=True)
        return result_list

    def withdraw(self, asset, address, amount):
        '''
        :param asset:
        :param address:
        :param amount:
        :return:
        '''
        params = {
            'currency': asset,
            'address': address,
            'amount': amount
        }
        url = "/v1/dw/withdraw/api/create"
        result = self.api_key_post(params, url)
        print('withdraw result: {}'.format(result))

        if result.get('status', 'error') == 'ok':
            return True
        else:
            return False

    def update(self, flags):
        '''
        :param flags: {"depth": True, 'trade': False}
        :return:
        '''
        self.unset_flags(flags)
        self.register_callbacks()

        while True:
            asyncio.sleep(1)
            if (self.check_flags(flags)):
                break
        return self

    async def update_depth(self, data_depth):
        list_of_ask = self.huobi_depth_format(data_depth['tick'], "asks")
        list_of_bid = self.huobi_depth_format(data_depth['tick'], "bids")
        self.depth = {"asks": list_of_ask, 'bids': list_of_bid}
        self.update_flags["depth"] = True

    async def _close_ws(self):
        await asyncio.sleep(5)
        await self.websocket.close()


    async def ws_handler(self):
        '''
        handle task in backthread
        :return:
        '''
        while True:
            try:
                compressData = await asyncio.wait_for(self.websocket.recv(), timeout=20)
            except Exception as ex:
                try:
                    self.error('Huobi ws_handler: %s' % ex)
                    await self.keep_connect()
                except Exception:
                    self.depth = {}
                    break
            else:

                result = gzip.decompress(compressData).decode('utf-8')
                result = json.loads(result)
                if "ping" in result:
                    pong = json.dumps({"pong": result["ping"]})
                    if self.websocket and self.websocket.open:
                        await self.websocket.send(pong)
                elif 'ch' in result:
                    await self.methods[result['ch']](result)


    def run(self):
        asyncio.set_event_loop(self.loop)
        update_order_info_event = threading.Event()
        self.updateOrderInfoThread(update_order_info_event, 1)
        while True:
            try:
                self.loop.run_until_complete(self.keep_connect())
                tasks = [self.ws_handler()]
                self.loop.run_until_complete(asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED))
                time.sleep(5)
            except Exception as ex:
                self.error(ex)

        # update_depth_event = threading.Event()
        # self.updateDepthThread(update_depth_event,1)



def test_buy_eth_use_usdt():
    os.environ[Constants.DQUANT_ENV] = "dev"
    loop = asyncio.get_event_loop()
    hb = HuobiRest("bch_btc", loop)
    hb.start()
    time.sleep(5)
    while True:
        print(hb.getDepth())
        time.sleep(2)


def test_sell_eth_use_usdt():
    os.environ[Constants.DQUANT_ENV] = "dev"
    loop = asyncio.new_event_loop()
    hb = HuobiRest("eth_usdt", loop)
    hb.start()
    #print(hb.getAccount())
    hb.withdraw('eth', '0x6596a07dc8ea1c5418f64267ce7ca4f38ea0e087', 0.025)
    #print(hb.get_our_history_orders())
    #result = hb.buy(amount=0.0011111111, price=0.00911111111)
    #print(result)
    #print(hb.getOrder(1877835396))


if __name__ == "__main__":
    #test_buy_eth_use_btc()
    #test_buy_eth_use_usdt()
    test_sell_eth_use_usdt()
    time.sleep(1000)