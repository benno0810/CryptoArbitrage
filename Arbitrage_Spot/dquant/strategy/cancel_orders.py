import os
import sys
sys.path.append('../../')
from dquant.markets._binance_spot_rest import Binance
from dquant.markets._bitfinex_spot_rest import TradingV1
# from dquant.markets._huobi_spot_rest import HuobiRest
from dquant.markets._okex_spot_rest import OkexSpotRest
from dquant.markets.market import Market
from dquant.util import Util

import sys
import queue
import collections
import base64
import hmac
import os
import datetime
import logging
from dquant.config import cfg
from dquant.constants import Constants
import hashlib
import json
import requests
import urllib.parse
import requests.adapters

requests.adapters.DEFAULT_RETRIES = 5
delay_time = 0.1

class HuobiRest(Market):
    def __init__(self, meta_code):
        market_currency, base_currency, symbol = self.parse_meta(meta_code)
        super().__init__(market_currency, base_currency, meta_code, cfg.get_float_config(Constants.HUOBI_FEE))
        self.apikey = cfg.get_config(Constants.HUOBI_APIKEY)
        self.apisec = cfg.get_config(Constants.HUOBI_APISEC)
        self.huobi_id = cfg.get_config(Constants.HUOBI_ID)
        self.strategy_id = cfg.get_config(Constants.HUOBI_STRATEGY_ID)
        self.ip_pid_sid = Util.bfx_get_gid(self.strategy_id)
        self.spot_account_id = cfg.get_config(Constants.HUOBI_SPOT_ID)
        self.minimum_amount = cfg.get_float_config(Constants.HUOBI_MINIMUM_AMOUNT)
        self.amount_precision = cfg.get_int_config(Constants.HUOBI_AMOUNT_PRECISION)
        self.price_precision = cfg.get_int_config(Constants.HUOBI_PRICE_PRECISION)
        self.symbol = symbol
        self.name = 'HuoBiPro'
        self.base_url_api = Constants.HUOBI_REST_BASE
        self.session = requests.session()
        self.timeout = Constants.OK_HTTP_TIMEOUT
        self.orders = []
        self.order_info_table = {}
        self.type_map = {'buy-limit':'buy', 'buy-market':'buy', 'sell-limit':'sell', 'sell-market':'sell'}
        self.order_result_required = False
        self.q_order_result = queue.Queue()
        self.hist = {'buy': collections.OrderedDict(), 'sell': collections.OrderedDict()}
        self.hist_lenth = 10

    def deleteOrder(self, order_id, tillOK=True):
        '''
        :param orderId:
        :param tillOK:
        :return: {'status': 'ok', 'data': '460960843'}
        '''
        while True:
            try:
                params = {}
                url = "/v1/order/orders/{0}/submitcancel".format(order_id)
                result = self.api_key_post(params, url)
                logging.debug('Huobi delete: %s' % result)
                # print(result)
                if result['status'] == 'ok':
                    try:
                        self.orders.remove(order_id)
                    except:
                        pass
                    return self.simpleGetOrder(order_id)

                if not result or result['status'] != 'ok':
                    self.updateOrderInfo(order_id)

                order_result = self.simpleGetOrder(order_id)
                if 'state' in order_result and order_result['state'] in ['canceled', 'filled', 'partial-canceled']:
                    try:
                        self.orders.remove(order_id)
                    except:
                        pass
                    return order_result
                self.error('Huobi Delete Order: %s' % order_result)
                continue
                    # return self.simpleGetOrder(order_id)
            except Exception as ex:
                self.error("Huobi cancel Order %s" % ex)
                if tillOK:
                    continue


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
        meta_table = {"eth_usdt": ("eth", "usdt", "ethusdt"),
                      "btc_usdt": ("btc", "usdt", "btcusdt"),
                      "eth_btc": ("eth", "btc", "ethbtc"),
                      "eos_eth": ("eos", "eth", "eoseth"),
                      "eos_btc": ("eos", "btc", "eosbtc"),
                      "bch_btc": ("bch", "btc", "bchbtc")}
        return meta_table[meta_code]

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


    def run(self):
        pass



def get_command():
    config_map = {'1':'Bitfinex', '2':'Binance', '3':'HuoBiPro', '4':'OKEX'}
    func_map = {'1':TradingV1,
                '2':Binance,
                '3':HuobiRest,
                '4':OkexSpotRest}
    if len(sys.argv) == 1:
        meta_code = 'eth_btc'
        for key, obj in func_map.items():
            print('cancel orders: %s...' % config_map[key])
            mkt = obj(meta_code)
            mkt.cancel_active_orders()
        print('done.')
    elif len(sys.argv) == 2:
        if sys.argv[1] in config_map:
            meta_code = 'eth_btc'
            print('cancel orders: %s...' % config_map[sys.argv[1]])
            mkt = func_map[sys.argv[1]](meta_code)
            mkt.cancel_active_orders()
            print('done.')
        else:
            meta_code = sys.argv[1]
            for key, obj in func_map.items():
                print('cancel orders: %s...' % config_map[key])
                mkt = obj(meta_code)
                mkt.cancel_active_orders()
            print('done.')
    elif len(sys.argv) == 3:
        if sys.argv[1] in config_map:
            meta_code = sys.argv[2]
            print('cancel orders: %s...' % config_map[sys.argv[1]])
            mkt = func_map[sys.argv[1]](meta_code)
            mkt.cancel_active_orders()
        else:
            meta_code = sys.argv[1]
            print('cancel orders: %s...' % config_map[sys.argv[2]])
            mkt = func_map[sys.argv[1]](meta_code)
            mkt.cancel_active_orders()
        print('done.')


def cancel_huobi_orders():
    meta_codes = ['eth_btc', 'eth_usdt', 'btc_usdt']
    for meta_code in meta_codes:
        print(meta_code)
        try:
            mkt = HuobiRest(meta_code)
            mkt.cancel_active_orders()
        except Exception as ex:
            print(ex)


if __name__ == '__main__':
    os.environ[Constants.DQUANT_ENV] = "dev"
    get_command()
