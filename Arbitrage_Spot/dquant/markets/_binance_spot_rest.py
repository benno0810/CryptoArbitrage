import queue
import sys
from operator import itemgetter

sys.path.append('../../')
import datetime
import hmac
import base64
import logging
import os

from dquant.config import cfg
from dquant.constants import Constants
from dquant.markets.market import Market
import hashlib
import time
import json
import requests
import urllib.parse
from urllib.parse import urlencode
# from util import *
import requests.adapters
from dquant.util import Util
from dquant.common.mongo_conn import MongoConnTrade


requests.adapters.DEFAULT_RETRIES = 5
delay_time = 0.1
logger = logging.getLogger(__name__)


class Binance(Market):
    PUBLIC_API_VERSION = 'v1'

    def __init__(self, meta_code):
        market_currency, base_currency, symbol = self.parse_meta(meta_code)
        super().__init__(market_currency, base_currency, meta_code, cfg.get_float_config(Constants.BINANCE_FEE))
        self.apikey = cfg.get_config(Constants.BINANCE_APIKEY)
        self.apisec = cfg.get_config(Constants.BINANCE_APISEC)
        self.binance_id = cfg.get_config(Constants.BINANCE_ID)
        self.strategy_id = cfg.get_config(Constants.BINANCE_STRATEGY_ID)
        self.fee_rate_taker = cfg.get_float_config(Constants.BINANCE_FEE_TAKER)
        # self.minimum_amount = cfg.get_config(Constants.BINANCE_MINIMUM_AMOUNT)
        self.name = 'Binance'
        self.symbol = symbol
        self.base_url = Constants.BINANCE_SPOT_REST_BASE
        self.session = requests.session()
        self.timeout = Constants.OK_HTTP_TIMEOUT
        self.db = MongoConnTrade().client.get_database('trade_binance')
        self.collection = self.db.get_collection(self.symbol.lower())

        [self.minimum_amount, self.price_precision, self.amount_precision] = cfg.get_precisions(self.name,
                                                                                                market_currency + base_currency)
        if not (self.price_precision and self.amount_precision):
            self.minimum_amount = cfg.get_float_config(Constants.BINANCE_MINIMUM_AMOUNT)
            self.amount_precision = cfg.get_int_config(Constants.BINANCE_AMOUNT_PRECISION)
            self.price_precision = cfg.get_int_config(Constants.BINANCE_PRICE_PRECISION)

        self.wsession = self._init_session()

    def _init_session(self):

        session = requests.session()
        session.headers.update({'Accept': 'application/json',
                                'User-Agent': 'binance/python',
                                'X-MBX-APIKEY': self.apikey})
        return session

    def _get_timestamp(self):
        return str(int(time.time())*1000)

    def _get_banned_seconds(self, response):
        # {'code': -1003, 'msg': 'Way too many requests; IP banned until 1515928731750.'}
        interval = None
        try:
            if response and 'code' in response and response['code'] == -1003:
                timestamp = response['msg'].split(" ")[-1][:-1]
                timestamp = int(timestamp) // 1000
                interval = timestamp - int(time.time())
                return interval
        except Exception:
            return interval


    def getAccount(self, coin=[], tillOK=True):

        error_c = 0
        res = None
        while True:
            try:
                params ={}
                params["timestamp"] = self._get_timestamp()
                params['signature'] = self.buildMySign(params)
                res = self.httpPost(self.base_url, Constants.BINANCE_USERINFO_RESOURCE_REST, params, 'get')
                if res and 'balances' in res and coin:
                    ans = {}
                    for c in coin:
                        ans[c.upper()] = 0.0
                    for c in res["balances"]:
                        if c["asset"].upper() in coin:
                            ans[c["asset"].upper()] = float(c["free"])
                    return ans
                if res and 'balances' in res and not coin:
                    ans = {}
                    coin = [self.market_currency, self.base_currency]
                    for c in coin:
                        ans[c.upper()] = 0.0
                    for c in res["balances"]:
                        if c["asset"].upper() in coin:
                            ans[c["asset"].upper()] = float(c["free"])
                    return ans
                self.error('Binance get account %s' % res)
                error_c += 1
                if tillOK:
                    time.sleep(1)
                    continue
                return res
            except Exception as ex:
                self.error("Binance login %s" % ex)
                error_c += 1
                time.sleep(1)
                if not tillOK:
                    return None
            finally:
                if error_c >= 5:
                    self.error("Binance getAccount Fital Error")
                    banned_seconds = self._get_banned_seconds(res)
                    raise TimeoutError(banned_seconds)

    def depth_format(self, list):
        ret = []
        for item in list:
            price = float(item[0])
            amount = float(item[1])
            ret.append({'price':price, 'amount':amount})
        return ret

    def getDepth(self,size=20,tillOK=True):
        s_time = time.time()
        error_c = 0
        res = None
        while True:
            try:
                params = 'symbol=%(symbol)s&limit=%(size)d' %{'symbol':self.symbol,'size':size}
                res = self.httpGet(self.base_url,Constants.BINANCE_DEPTH_RESOURCE_REST,params)
                if not res or "code" in res or 'bids' not in res:
                    self.error('Binance getDepth %s' % res)
                    error_c += 1
                    if tillOK:
                        time.sleep(0.5)
                        continue
                bid_list = self.depth_format(res['bids'])
                ask_list = self.depth_format(res['asks'])
                self.compute_latency(s_time, 'depth')
                return {'bids':bid_list, 'asks': ask_list}
            except Exception as ex:
                self.error("Binance getDepth %s" % ex)
                error_c += 1
                if tillOK:
                    time.sleep(0.5)
                    continue
                self.compute_latency(s_time, 'depth')
                return {}
            finally:
                if error_c >= 5:
                    self.error("Binance getDepth Fital Error")
                    banned_seconds = self._get_banned_seconds(res)
                    raise TimeoutError(banned_seconds)

    def buy(self,amount,price=-1):
        '''
        :param amount:
        :param price:
        :return: 	{'symbol': 'ETHUSDT', 'orderId': 9354635, 'clientOrderId': '127_0_0_1_0_1068',
            'transactTime': 1514513350124, 'price': '700.00000000', 'origQty': '0.01000000', 'executedQty': '0.01000000',
            'status': 'FILLED', 'timeInForce': 'GTC', 'type': 'LIMIT', 'side': 'SELL'}
        '''
        # 默认的order_result

        s_time = time.time()

        order_result = Util.build_order_result(
            status=True, side='buy', trade_pair=self.symbol,
            price=price, platform_id='binance',
            amount_orig=amount, amount_filled=0
        )
        while True:
            try:
                params = {'symbol':self.symbol,}

                if price > 0:
                    # params['price'] = price
                    params['price'] = self._surpress_scientific_notation(price, self.price_precision)
                    params['type'] = 'LIMIT'
                    params['timeInForce']="GTC"
                else:
                    params["type"] = "MARKET"
                # params['quantity'] = abs(amount)
                params['quantity'] = self._surpress_scientific_notation(abs(amount), self.amount_precision)
                params["side"] = "BUY"
                params['newClientOrderId'] = Util.bnc_get_cid(self.strategy_id)
                params["timestamp"] = self._get_timestamp()
                params['signature'] = self.buildMySign(params)
                res = self.httpPost(self.base_url,Constants.BINANCE_TRADE_RESOURCE_REST,params,timeout=20.0)

                if not res or "code" in res or 'orderId' not in res:
                    # logging.error("Binance: buy %s" % res)
                    # "Timestamp for this request was 1000ms ahead of the server's time."
                    if res['code'] == -1021:
                        self.error("Binance: buy %s Retry" % res)
                        time.sleep(1)
                        continue
                    self.error("Binance: buy %s" % res)
                    order_result.update({
                        "status": False,
                        "error_message": Constants.ORDER_RESULT_ERROR['timeout']
                    })
                    self.q_orders_result.put(order_result)
                    self.compute_latency(s_time, 'buy')
                    return order_result

                if price > 0 and params['type']:
                    maker_res = Util.build_order_store(status=True, order_id=res['orderId'], side=params["type"],
                                                       trade_pair=res['symbol'], price=res['price'],
                                                       amount_filled=res['executedQty'],
                                                       amount_orig=res['origQty'], time_stamp=res['transactTime'],
                                                       client_order_id=res['clientOrderId'],
                                                       platform_name='binance', platform_account_id=self.binance_id,
                                                       strategy_id=self.strategy_id, fee_rate=self.fee_rate)
                    self.q_maker.put(maker_res)
                # reset order_result
                order_result = Util.build_order_result(
                    status=True, order_id=res['orderId'],
                    side=res['side'].lower(),
                    trade_pair=res['symbol'], price=res['price'],
                    amount_filled=res['executedQty'],
                    amount_orig=res['origQty'],
                    time_stamp=res['transactTime'],
                    client_order_id=res['clientOrderId'],
                    platform_id='binance'
                )
                self.q_orders_result.put(order_result)
                self.compute_latency(s_time, 'buy')
                return order_result
            except Exception as ex:
                print('ex: {}'.format(ex))
                self.error("Binance: buy %s" % ex)
                order_result.update({
                    "status": False,
                    "error_message": "butest_buy_eos_use_ethy fail"
                })
                self.q_orders_result.put(order_result)
                self.compute_latency(s_time, 'buy')
                return order_result

    def sell(self,amount,price=-1):
        '''
        :param volume:
        :param price:
        :return: {'symbol': 'ETHBTC', 'orderId': 22881766, 'clientOrderId': 'ZX1LP7ArGCkBjHEcdMl7ib',
            'transactTime': 1512126833548, 'price': '0.00000000', 'origQty': '0.01000000', 'executedQty': '0.01000000',
            'status': 'FILLED', 'timeInForce': 'GTC', 'type': 'MARKET', 'side': 'SELL'}
        '''
        # default order result
        order_result = Util.build_order_result(
            status=True, trade_pair=self.symbol, price=price,
            side='sell', platform_id='binance',
            amount_orig=amount, amount_filled=0
        )
        while True:
            try:
                params = {'symbol':self.symbol,}
                if price>0:
                    # params['price'] = price
                    params['price'] = self._surpress_scientific_notation(price, self.price_precision)
                    params['type'] = 'LIMIT'
                    params['timeInForce']="GTC"
                else:
                    params["type"] = "MARKET"
                # params['quantity'] = abs(amount)
                params['quantity'] = self._surpress_scientific_notation(abs(amount), self.amount_precision)
                params['newClientOrderId'] = Util.bnc_get_cid(self.strategy_id)
                params["timestamp"] = self._get_timestamp()
                params["side"] = "SELL"
                params['signature'] = self.buildMySign(params)
                res = self.httpPost(self.base_url,Constants.BINANCE_TRADE_RESOURCE_REST,params,timeout=20.0)

                if not res or "code" in res or 'orderId' not in res:
                    if res['code'] == -1021:
                        self.error("Binance: sell %s Retry" % res)
                        time.sleep(1)
                        continue
                    self.error("Binance: sell %s" % res)
                    order_result.update({
                        "status": False,
                        "error_message": Constants.ORDER_RESULT_ERROR['timeout']
                    })
                    self.q_orders_result.put(order_result)
                    return order_result

                if price > 0 and params['type']:
                    maker_res = Util.build_order_store(status=True, order_id=res['orderId'], side=params["type"],
                                                       trade_pair=res['symbol'], price=res['price'],
                                                       amount_filled=res['executedQty'],
                                                       amount_orig=res['origQty'], time_stamp=res['transactTime'],
                                                       client_order_id=res['clientOrderId'],
                                                       platform_name='binance', platform_account_id=self.binance_id,
                                                       strategy_id=self.strategy_id, fee_rate=self.fee_rate_taker)
                    self.q_maker.put(maker_res)
                order_result = Util.build_order_result(
                    status=True, order_id=res['orderId'],
                    side=res['side'].lower(),
                    trade_pair=res['symbol'], price=res['price'],
                    amount_filled=res['executedQty'],
                    amount_orig=res['origQty'], time_stamp=res['transactTime'],
                    client_order_id=res['clientOrderId'],
                    platform_id='binance'
                )
                self.q_orders_result.put(order_result)
                return order_result
            except Exception as ex:
                self.error("Binance: sell %s" % ex)
                order_result.update({
                    'status': False,
                    "error_message": "sell fail"
                })
                self.q_orders_result.put(order_result)
                return order_result

    def deleteOrder(self,order_id,tillOK= True):
        '''
        :param orderId:
        :param tillOK:
        :return: {'symbol': 'ETHBTC', 'origClientOrderId': 'aoO1hzBrf920iMvtpBPeAk', 'orderId': 22882359, 'clientOrderId': 'kK4YLlIy2lHkyH271o1qtD'}
        '''
        s_time = time.time()
        while True:
            try:
                params = {
                     'symbol':self.symbol,
                     'orderId':order_id
                }
                params["timestamp"] = self._get_timestamp()
                params['signature'] = self.buildMySign(params)
                res = self.httpPost(self.base_url,Constants.BINANCE_TRADE_RESOURCE_REST,params,'delete')
                # print res
                if not res or "code" in res:
                    # {'code': -2011, 'msg': 'UNKNOWN_ORDER'}
                    if res['code'] == -2011:
                        time.sleep(0.5)
                        result = self.getOrder(order_id)
                        break
                    self.error('Binance: cancel Order %s' % res)
                    if tillOK:
                        time.sleep(1)
                        continue
                result = self.getOrder(order_id)
                break
            except Exception as ex:
                self.error("Binance: cancel Order %s" % ex)
                if tillOK:
                    time.sleep(1)
                    continue
                result = Util.build_order_result(status=False, order_id=order_id)
                break
        # 记录result
        result['platform_id'] = 'binance'
        self.q_cancelled_orders.put(result)
        self.compute_latency(s_time, 'cancel')
        return result

    def getOrder(self,order_id,tillOK=True):
        while True:
            try:
                params = {'symbol':self.symbol, 'orderId':order_id }
                params["timestamp"] = self._get_timestamp()
                params['signature'] = self.buildMySign(params)
                res = self.httpPost(self.base_url,Constants.BINANCE_TRADE_RESOURCE_REST,params,'get')
                # print(res)
                if not res or "code" in res:
                    self.error('Binance: getOrder %s ' % res)
                    if tillOK:
                        time.sleep(1)
                        continue
                return Util.build_order_result(status=True, order_id=res['orderId'], side=res['side'].lower(),
                                               trade_pair=res['symbol'], price=res['price'],
                                               amount_filled=res['executedQty'],
                                               amount_orig=res['origQty'], time_stamp=res['time'])
            except Exception as ex:
                self.error("Binance: get Order %s " % ex)
                if tillOK:
                    time.sleep(1)
                    continue
                return Util.build_order_result(status=False, order_id=order_id)

    def get_active_orders(self, tillOK=True):

        params = {'symbol': self.symbol}
        params["timestamp"] = str(int(time.time()) * 1000)
        params['signature'] = self.buildMySign(params)
        #res = self.httpPost(self.base_url, '/api/v1/allOrders', params, 'get')
        res = self.httpPost(self.base_url, '/api/v1/openOrders', params, 'get')
        return res

    def cancel_active_orders(self, tillOK=True):
        '''Cancel an active order.'''

        res = {'success':[], 'fail': []}
        orders = self.get_active_orders()
        print('orders: ', orders)
        if not orders:
            return res

        order_ids = [ e['orderId'] for e in orders if 'orderId' in e]

        for order_id in order_ids:
            params = {'symbol': self.symbol}
            params["timestamp"] = str(int(time.time()) * 1000)
            params['orderId'] = order_id
            params['signature'] = self.buildMySign(params)
            rsp = self.httpPost(self.base_url, '/api/v1/order', params, 'delete')
            if 'orderId' in rsp:
                res['success'].append(rsp['orderId'])
            else:
                res['fail'].append(order_id)
        return res

    def api_key_get(self, params, request_path):
        method = 'GET'
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        params_sign = {'AccessKeyId': self.apikey,
                       'SignatureMethod': 'HmacSHA256',
                       #'SignatureVersion': '2',
                       'Timestamp': timestamp}
        params_sign.update(params)

        host_url = self.base_url
        host_name = urllib.parse.urlparse(host_url).hostname
        host_name = host_name.lower()

        params['signature'] = self.buildMySign_hmac(params_sign, method, host_name, request_path, self.apisec)

        url = host_url + request_path
        return self.http_get_request(url, params)

    def api_key_post(self, params, request_path):
        method = 'POST'
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        params_to_sign = {'AccessKeyId': self.apikey,
                          'SignatureMethod': 'HmacSHA256',
                          #'SignatureVersion': '2',
                          'Timestamp': timestamp}

        host_url = self.base_url
        host_name = urllib.parse.urlparse(host_url).hostname
        host_name = host_name.lower()
        params_to_sign['Signature'] = self.buildMySign_hmac(params_to_sign, method, host_name, request_path, self.apisec)
        url = host_url + request_path + '?' + urllib.parse.urlencode(params_to_sign)
        return self.http_post_request(url, params)

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
            if response.status_code == 429:
                time.sleep(1)
        except BaseException as e:
            print("httpPost failed, detail is:%s,%s" % (response.text, e))
        return {}

    def http_get_request(self, url, params, add_to_headers=None):
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "X-MBX-APIKEY": self.apikey
        }
        if add_to_headers:
            headers.update(add_to_headers)

        postdata = urllib.parse.urlencode(params)

        try:
            response = requests.get(url, postdata, headers=headers, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 429:
                time.sleep(1)
        except BaseException as e:
            print("httpGet failed, detail is:%s" % e)
        return {}

    def buildMySign_hmac(self, params, method, host_url, request_path, secret_key):
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

    def buildMySign(self,params):
        sign = ''
        for key in params.keys():
            sign += key + '=' + str(params[key]) +'&'
        data = self.apisec+'|'+sign[:-1]
        mysign = hashlib.sha256(data.encode("utf8")).hexdigest().upper()
        # print(mysign)
        return mysign

    def _surpress_scientific_notation(self, float_number, precision):
        _format = "{" + ":.{}f".format(precision) + "}"
        float_str = _format.format(float_number)
        return float_str

    def httpGet(self,url,resource,params=''):
        # conn = http.client.HTTPSConnection(url, timeout=10)
        if params:
            response = self.session.get(url=url+resource + '?' + params,timeout=5.0)
        else:
            response = self.session.get(url = url+resource,timeout=5.0)
        # response = conn.getresponse()
        data = response.text
        if response.status_code == 429:
            time.sleep(1)
        # data = response.text.decode('utf-8')
        try:
            result = json.loads(data)
            return result
        except Exception:
            self.error('Binance HttpGet: %s' % data)
            return None

    def httpPost(self,url,resource,params,type='post',timeout=5.0):
         headers = {
                "Content-type" : "application/x-www-form-urlencoded",
                "X-MBX-APIKEY" : self.apikey
         }
         temp_params = urllib.parse.urlencode(params)
         if type == "post":
             res = self.session.post(url = url+resource,data = temp_params,headers = headers,timeout=timeout)
         elif type == "get":
             res = self.session.get(url = url+resource+"?"+temp_params,headers = headers,timeout=timeout)
         elif type == "delete":
             res = self.session.delete(url=url+resource,data = temp_params,headers = headers,timeout=timeout)
         data = res.text
         #params.clear()

         if res.status_code == 429:
             time.sleep(1)
         # print('httpPost res: ', res.json(), 'status_code: ', res.status_code)

         try:
            result = json.loads(data)
            return result
         except Exception:
             self.error('Binance HttpPost: %s' % data)
             return None

         # return json.loads(data)

    def parse_meta(self, meta_code):
        meta_table = {'eth_usdt': ("ETH", "USDT", "ETHUSDT"),
                      'btc_usdt': ("BTC", "USDT", "BTCUSDT"),
                      'eth_btc': ("ETH", "BTC", "ETHBTC"),
                      'bnb_btc': ('BNB', 'BTC', 'BNBBTC'),
                      'bnb_usdt': ('BNB', 'USDT', 'BNBUSDT'),
                      'ltc_eth': ('LTC', 'ETH', 'LTCETH'),
                      'ltc_bnb': ('LTC', 'BNB', 'LTCBNB'),
                      'bcc_usdt': ('BCC', 'USDT', 'BCCUSDT'),
                      'bcc_bnb': ('BCC', 'BNB', 'BCCBNB'),
                      'bcc_btc': ('BCC', 'BTC', 'BCCBTC'),
                      'bch_btc': ('BCC', 'BTC', 'BCCBTC'),
                      'ven_bnb': ('VEN', 'BNB', 'VENBNB'),
                      'bnb_eth': ('BNB', 'ETH', 'BNBETH'),
                      'ven_eth': ('VEN', 'ETH', 'VENETH'),
                      'bcc_eth': ('BCC', 'ETH', 'BCCETH'),
                      'bch_eth': ('BCC', 'ETH', 'BCCETH'),
                      'ltc_btc': ('LTC', 'BTC', 'LTCBTC'),
                      'ltc_usdt': ('LTC', 'USDT', 'LTCUSDT'),
                      'eos_eth': ('EOS', 'ETH', 'EOSETH'),
                      'eos_btc': ('EOS', 'BTC', 'EOSBTC'),
                      }

        return meta_table[meta_code]

    def request(self, resource, params, type):
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "X-MBX-APIKEY": self.apikey
        }
        if type == "post":
            temp_params = urllib.parse.urlencode(params)
            res = self.session.post(url=self.base_url + resource, data=temp_params, timeout=self.timeout, headers=headers)
        elif type == "get":
            res = self.session.get(url=self.base_url + resource, params=params, timeout=self.timeout, headers=headers)
        if res.status_code == 200:
            return json.loads(res.content, encoding='utf-8')
        else:
            # print(res)
            logger.exception("request error")
        return res.json()

    def get_trades(self):
        '''
         _id       datetime obj
         tid       "id": 28457,
         price     "price": "4.00000100",
         amount    "qty": "12.00000000",
         timestamp  "time": 1499865549590,
         type      "isBuyerMaker": true,

         input:
             symbol
             limit: Default 500; max 500.
             fromId: TradeId to fetch from. Default gets most recent trades.

         死循环。每轮获取500个。每轮保存id的集合。找出max(id)。
         下一轮从max(id)开始找。
        '''

        from_id = 1
        params = {'symbol': self.symbol, 'limit': 500}
        while True:
            try:
                params['fromId'] = from_id
                tids = []
                res = self.request(Constants.BINANCE_TRADES_REST, params=params, type='get')
                print('res: ', res, 'symbol: ', self.symbol)
                to_db = []
                for one in res:
                    the_id = one['id']
                    tids.append(the_id)

                    tmp = {
                        '_id': datetime.datetime.now(),
                        'tid': one['id'],
                        'price': one['price'],
                        'amount': one['qty'],
                        'timestamp': one['time'],
                        'type': True if one['isBuyerMaker'] else False,
                    }
                    to_db.append(tmp)
                    time.sleep(0.001)

                if to_db:
                    self.collection.insert(to_db)
                    from_id = max(tids) + 1

                # 睡10min。没必要跑那么快
                time.sleep(600)
            except Exception as e:
                print(e)
                continue

    def _generate_v3_signature(self, data):

        ordered_data = self._order_params(data)
        query_string = '&'.join(["{}={}".format(d[0], d[1]) for d in ordered_data])
        m = hmac.new(self.apisec.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        return m.hexdigest()

    def get_our_history_orders(self, limit=500, order_id=None, tillOK=True):
        '''
        If orderId is set, it will get orders >= that orderId. Otherwise most recent orders are returned.

        :param
            limit: Default 500; max 500.
            tillOK:
        :return:
        '''
        url = '/api/v1/allOrders'
        while True:
            try:
                params = {'symbol': self.symbol, 'limit': limit}
                if order_id:
                    params['orderId'] = int(order_id)
                params["timestamp"] = self._get_timestamp()
                params['signature'] = self.buildMySign(params)
                res = self.httpPost(self.base_url, url, params, 'get')
                # print(res)
                if not res or "code" in res:
                    self.error('Binance: getOrder %s ' % res)
                    if tillOK:
                        time.sleep(10)
                        continue
                done = ['FILLED', 'PARTIALLY_FILLED']
                ress = [e for e in res if e['status'] in done]
                return ress
            except Exception as ex:
                self.error("Binance: get Order %s " % ex)

    def get_our_history_trades(self, limit=500, order_id=None, tillOK=True):
        '''
        If orderId is set, it will get orders >= that orderId. Otherwise most recent orders are returned.

        :param
            limit: Default 500; max 500.
            tillOK:
        :return:
        '''
        url = '/api/v1/myTrades'
        while True:
            try:
                params = {'symbol': self.symbol, 'limit': limit}
                if order_id:
                    params['fromId'] = int(order_id)
                params["timestamp"] = self._get_timestamp()
                params['signature'] = self.buildMySign(params)
                res = self.httpPost(self.base_url, url, params, 'get')
                # print(res)
                if not res or "code" in res:
                    self.error('Binance: getOrder %s ' % res)
                    if tillOK:
                        time.sleep(10)
                        continue
                # done = ['FILLED', 'PARTIALLY_FILLED']
                # ress = [e for e in res if e['status'] in done]
                return res
            except Exception as ex:
                self.error("Binance: get Order %s " % ex)

    def _order_params(self, data):
        """Convert params to list with signature as last element
        :param data:
        :return:
        """
        has_signature = False
        params = []
        for key, value in data.items():
            if key == 'signature':
                has_signature = True
            else:
                params.append((key, value))
        # sort parameters by key
        params.sort(key=itemgetter(0))
        if has_signature:
            params.append(('signature', data['signature']))
            return params

    def _generate_signature(self, data):

        query_string = urlencode(data)
        m = hmac.new(self.apisec.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        return m.hexdigest()

    def withdraw(self, asset, address, amount):
        '''
        :param asset: btc还是eth...
        :param address: 目标地址
        :param amount: 币的数量
        :param timestamp: 时间戳
        :return:
        '''
        params = {}

        params['data'] = {
           'asset': asset,
           'address': address,
           'amount': amount,
         }
        params['data']["timestamp"] = self._get_timestamp()

        params['data']['signature'] = self.buildMySign(params)

        headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "X-MBX-APIKEY": self.apikey,
            #"payload": json.dumps(params['data'])
        }

        #params['headers'] = headers
        res = self._request('post', '{}/{}'.format(self.base_url,'/wapi/v3/withdraw.html'), True, True, **params)

        #res = requests.post('{}{}'.format(self.base_url,'/wapi/v1/withdraw.html'), data=json.dumps(params), headers=headers)
        #res = requests.post('{}/{}'.format(self.base_url,'/wapi/v3/withdraw.html'), data=params, headers=headers)

        print('withdraw res: {}, type(res): {}'.format(res, type(res)))

        return res['success']

    def _request(self, method, uri, signed, force_params=False, **kwargs):

        data = kwargs.get('data', None)
        if data and isinstance(data, dict):
            kwargs['data'] = data
        if signed:
            # generate signature
            kwargs['data']['timestamp'] = int(time.time() * 1000)

            print('data: {}'.format(data))

            kwargs['data']['signature'] = self._generate_signature(kwargs['data'])
            #kwargs['data']['signature'] = self._generate_v3_signature(kwargs['data'])


        if data and (method == 'get' or force_params):
            kwargs['params'] = self._order_params(kwargs['data'])
            del(kwargs['data'])

        response = getattr(self.wsession, method)(uri, **kwargs)
        return self._handle_response(response)

    def _handle_response(self, response):
        """Internal helper for handling API responses from the Binance server.
        Raises the appropriate exceptions when necessary; otherwise, returns the
        response.
        """
        if not str(response.status_code).startswith('2'):
            return {'msg': 'api error'}
            #raise BinanceAPIException(response)
        try:
            return response.json()
        except ValueError:
            #raise BinanceRequestException('Invalid Response: %s' % response.text)
            return {'msg': 'invalid response'}




def test_buy_eth_use_usdt():

    os.environ[Constants.DQUANT_ENV] = "dev"
    bi = Binance("eth_btc")
    bi.start()
    #print('sell')
    # print(bi.getAccount())
    res = bi.sell(amount=0.1, price=0.09)
    id = res['order_id']
    print(bi.deleteOrder(id))
    #print(bi.get_active_orders())
    #print('cancel')
    #print(bi.cancel_active_orders())
    #print('get')
    #print(bi.get_active_orders())
    # print(bi.getOrder(51774226))
    #print(bi.deleteOrder(10118518))
    #print(bi.buy(0.01))
    #print(bi.get_trades())


def test_buy_eos_use_eth():
    os.environ[Constants.DQUANT_ENV] = "dev"
    bi = Binance("btc_usdt")
    #print(bi.sell(0.1))
    #print(bi.buy(0.1))
    print(bi.getAccount())
    #print(bi.getAccount())
    #print(bi.get_trades())

def test_buy_bch_use_eth():
    os.environ[Constants.DQUANT_ENV] = "dev"
    bi = Binance("eth_usdt")
    #print(bi.sell(0.1, price=0.1))
    #print(bi.buy(0.04))
    #bi.getDepth()
    #print(bi.getAccount())
    # bi转到huobi 0.1个eth
    bi.withdraw('usdt', '0x5d38836532ee39ac341b0549d4290963981dda0b', 100)

if __name__ == "__main__":
    #test_buy_eos_use_eth()
    test_buy_bch_use_eth()