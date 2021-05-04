import sys
sys.path.append('../../')
import base64
import hmac
import os

import datetime

import logging

from requests import RequestException

from dquant.config import cfg
from dquant.constants import Constants
import hashlib
import time
import json
import requests
import urllib.parse
import requests.adapters

from dquant.markets.market import Market
from dquant.common.mongo_conn import MongoConnTrade

requests.adapters.DEFAULT_RETRIES = 5
delay_time = 0.1
logger = logging.getLogger(__name__)
class OkexSpotRest(Market):
    def __init__(self, meta_code):
        market_currency, base_currency, symbol = self.parse_meta(meta_code)
        super().__init__(market_currency, base_currency, meta_code, cfg.get_float_config(Constants.OKEX_FEE))
        self.apikey = cfg.get_config(Constants.OKEX_APIKEY)
        self.apisec = cfg.get_config(Constants.OKEX_APISEC)
        self.strategy_id = cfg.get_config(Constants.OKEX_STRATEGY_ID)
        self.name = 'OKEX'
        self.symbol = symbol
        # print(self.name, market_currency+base_currency, cfg.get_precisions(self.name, market_currency+base_currency))
        [self.minimum_amount, self.price_precision, self.amount_precision] = cfg.get_precisions(self.name, market_currency+base_currency)
        if not (self.price_precision and self.amount_precision):
            self.minimum_amount = cfg.get_config(Constants.OKEX_MINIMUM_AMOUNT)
            self.amount_precision = cfg.get_int_config(Constants.OKEX_AMOUNT_PRECISION)
            self.price_precision = cfg.get_int_config(Constants.OKEX_PRICE_PRECISION)
        self.base_url = Constants.OKEX_SPOT_REST_BASE
        self.session = requests.session()
        self.timeout = Constants.OK_HTTP_TIMEOUT
        self.db = MongoConnTrade().client.get_database('trade_ok')
        self.collection = self.db.get_collection(self.symbol.lower())

    def buy_step_by_step(self, price_to_be_buy_spot, times):
        # 价格乘数
        price_list=[]
        ret = []
        ratio = 1.1
        times = int(times)
        price_to_be_buy_spot = int(price_to_be_buy_spot)
        ask_1_price = self.getDepth()['asks'][0]['price']
        # 如果不够卖times*ratio次，一次成交
        if price_to_be_buy_spot < float(self.minimum_amount) * times * float(ask_1_price) * ratio:
            logger.info("OKEXSpot buy_step_by_step price: %s" % price_to_be_buy_spot)

            ret = [self.buy(price=price_to_be_buy_spot)]
        else:
            first9 = int(price_to_be_buy_spot/times)
            for i in range(times-1):
                price_list.append(first9)
            price_list.append(price_to_be_buy_spot-(times-1)*first9)
            logger.info("OKEXSpot buy_step_by_step price: %s" % price_list)
            # print(price_list)
            for piece_price in price_list:
                result = self.buy(price=piece_price)
                ret.append(result)
        logger.info("OKEXSpot buy_step_by_step result: %s" % price_list)
        return ret

    def get_sell_balance_for_future(self):
        balance = self.getAccount(coin=[self.market_currency])[self.market_currency]
        bid_1_price = self.getDepth()['bids'][0]['price']
        return balance * bid_1_price

    def get_buy_balance_for_future(self):
        balance = self.getAccount(coin=[self.base_currency])[self.base_currency]
        # bid_1_price = self.getDepth()['bids'][0]['price']
        return balance

    def get_ticker(self, tillOK=True):
        params = {
            'symbol': self.symbol,
        }
        while True:
            try:
                res = self.request(Constants.OKEX_SPOT_TICKER_REST, params, 'get')
                if 'ticker' in res:
                    return res
                elif tillOK:
                    time.sleep(0.5)
                    continue
                else:
                    return None
            except Exception as ex:
                logger.error("OKEXFuture Rest get_ticker: %s, Retry" % ex)
                if tillOK:
                    time.sleep(0.5)
                    continue
                return None

    def getAccount(self, coin=[]):
        res = self.okex_request(api_url=Constants.OKEX_SPOT_USERINFO_REST)
        if res['result'] is True:
            if coin:
                ret = {}
                for c in coin:
                    if c.lower() in res["info"]["funds"]["free"]:
                        ret[c.lower()] = float(res["info"]["funds"]["free"][c.lower()])
                    else:
                        ret[c.lower()] = 0.0
                return ret
            else:
                return res["info"]["funds"]["free"]

    def depth_format(self, list):
        ret = []
        for item in list:
            price = float(item[0])
            amount = float(item[1])
            ret.append({'price':price, 'amount':amount})
        return ret

    def getDepth(self, tillOK=True):
        params = {"symbol": self.symbol,}
        while True:
            try:
                res = self.request(Constants.OKEX_SPOT_DEPTH_RESOURCE_REST, params, "get")
                # print(res)
                list_of_ask = self.depth_format(res['asks'])
                list_of_bid = self.depth_format(res['bids'])
                list_of_ask.reverse()
                return {"asks": list_of_ask, 'bids': list_of_bid}
            except Exception as ex:
                logger.error("getDepth: %s" % ex)
                if tillOK:
                    continue
                return None

    def get_trades(self):
        '''
        _id         datetime obj
        tid         "tid": "230433",
        price       "price": 787.71,
        amount      "amount": 0.003,
        timestamp   "date_ms": "1367130137000",
        type        "type": "sell"
        symbol

        input:
        symbol:
        since: get recently 600 pieces of data starting from the given tid

        文档写返回tid后的最近600个。经测试是60个。即无论如何只能获取到60个。
        所以获取测试是这个程序在死循环。不停的获取最近60个。每次的60个和上次的60个比较，重复的不入库，否则入库。

        output:
            _id         datetime obj
            tid         "tid": "230433",
            price       "price": 787.71,
            amount      "amount": 0.003,
            timestamp   "date_ms": "1367130137000",
            type        "type": "sell"
        '''

        params = {'symbol': self.symbol, 'since': 1}
        tids_last = []

        while True:
            tids = []
            try:
                res = self.request(Constants.OKEX_SPOT_TRADES_REST, params=params, type='get')
                if 'error_code' in res:
                    time.sleep(1)
                    continue
                to_db = []
                for one in res:
                    the_id = one['tid']
                    tids.append(the_id)

                    if the_id in tids_last:
                        continue
                    tmp = {
                        '_id': datetime.datetime.now(),
                        'tid': one['tid'],
                        'price': one['price'],
                        'amount': one['amount'],
                        'timestamp': one['date_ms'],
                        'type': one['type'],
                    }
                    to_db.append(tmp)

                    time.sleep(0.001)
                if to_db:
                    self.collection.insert(to_db)
                    print(len(to_db))

                tids_last = tids
                time.sleep(50)
            except Exception as e:
                logger.error('get_trades error: %s' % e)
                continue

    def buy(self, amount=None, price=-1):
        '''
        :param amount:交易数量 [BTC >= 0.01 / LTC >= 0.1 / ETH >= 0.01  市价买单不传amount
        :param price: 下单价格 [限价买单(必填)：0-1000000 | 市价买单(必填)： BTC金额>0.01*卖一价 / LTC金额>0.1*卖一价 / ETH金额>0.01*卖一价)]
        :return:
        '''
        try:
            if price < 0:
                logger.error('okex market buy: price is required, amount=None')
                return None
            price = str(round(abs(float(price)), self.price_precision))
            type = "buy" if amount else "buy_market"
            if amount:
                amount = round(abs(float(amount)), self.amount_precision)
            result = self.okex_request(api_url=Constants.OKEX_SPOT_TRADE_REST, amount=amount, price=price, type=type)
            logger.info("OKEXSpot buy result: %s" % result)
            if not result:
                logger.error("buy: %s" % result)
                return None
            if "result" in result and result["result"] is not True:
                logger.error("buy: %s" % result)
                return None
            return result
        except Exception as ex:
            logger.error("buy %s" % ex)
            return None

    def sell(self,amount, price=-1):
        '''
        :param amount: 交易数量 [（必填）：BTC >= 0.01 / LTC >= 0.1 / ETH >= 0.01 ]
        :param price:下单价格 [市价卖单不传price]
        :return:
        '''
        try:
            amount = round(abs(float(amount)), self.amount_precision)
            if price > 0:
                price = str(round(abs(float(price)), self.price_precision))
                type = "sell"
            else:
                price = None
                type = 'sell_market'
            result = self.okex_request(api_url=Constants.OKEX_SPOT_TRADE_REST, amount=amount, price=price, type=type)
            if not result:
                logger.error("sell %s" % result)
                return None
            if result["result"] is not True:
                logger.error("sell: %s" % result)
                return None
            return result
        except Exception as ex:
            logger.error("sell %s" % ex)
            return None

    def deleteOrder(self,order_id,tillOK= True):
        '''
        :param orderId:
        :param tillOK:
        :return: {'symbol': 'ETHBTC', 'origClientOrderId': 'aoO1hzBrf920iMvtpBPeAk', 'orderId': 22882359, 'clientOrderId': 'kK4YLlIy2lHkyH271o1qtD'}
        '''
        while True:
            try:
                res = self.okex_request(order_id=order_id, api_url=Constants.OKEX_SPOT_DELETE_ORDER_REST)
                if 'result' in res:
                    if res['result'] == True:
                        return res
                if tillOK ==True:
                    continue
                else:
                    logger.error(res)
                    break
            except Exception as ex:
                logger.exception("message")
                if tillOK:
                    continue
                return None

    def getOrder(self,order_id=None,tillOK=True):
        while True:
            try:
                order_id = int(order_id) if order_id else -1
                res = self.okex_request(api_url=Constants.OKEX_SPOT_ORDERINFO_REST, order_id=order_id)
                if res['result'] is True:
                    return res["orders"]
                if tillOK:
                    continue
                else:
                    logger.error('getOrder: %s' % res)
                    return None
            except Exception as ex:
                logger.error('getOrder: %s' % ex)
                if tillOK:
                    continue
                else:
                    return None

    def get_orders(self,orders_id, tillOK=True):
        while True:
            try:
                order_id_query_string = ''
                for order_id in orders_id:
                    order_id_query_string += (str(order_id) + ',')
                res = self.okex_request(api_url=Constants.OKEX_SPOT_ORDERSINFO_REST, order_id_query_string=order_id_query_string)
                # print(res)
                if res['result'] is True:
                    return res["orders"]
                if tillOK:
                    continue
                else:
                    logger.error('get_orders: %s' % res)
                    return None
            except Exception as ex:
                logger.error('get_orders: %s' % ex)
                if tillOK:
                    continue
                else:
                    return None

    def get_active_orders(self):
        return self.getOrder(order_id=-1)

    def cancel_active_orders(self):
        order_ids = [e['order_id'] for e in self.get_active_orders()]
        lens = len(order_ids)
        print(lens, order_ids)
        try:
           for i in range(0, lens, 3):
                unit = order_ids[i:i+3]
                print("canceling", unit)
                tlen = len(unit)
                if tlen == 3:
                    ids = '{},{},{}'.format(order_ids[i:i+3][0],order_ids[i:i+3][1],order_ids[i:i+3][2])
                elif tlen == 2:
                    ids = '{},{}'.format(order_ids[i:i+3][0],order_ids[i:i+3][1])
                elif tlen == 1:
                    ids = order_ids[i:i+3][0]
                res = self.okex_request(order_id=ids, api_url=Constants.OKEX_SPOT_DELETE_ORDER_REST)
                print(res)
        except Exception as ex:
            print(ex)
            logger.exception(ex)
        return {}

    def buildMySign(self, params, secretKey):
        sign = ''
        for key in sorted(params.keys()):
            sign += key + '=' + str(params[key]) + '&'
        data = sign + 'secret_key=' + secretKey
        return hashlib.md5(data.encode("utf8")).hexdigest().upper()

    def withdraw(self, asset, address, amount, chargefee):
        '''
        :param asset:
        :param address:
        :param amount:
        :return:
        '''
        params = {
            'api_key': self.apikey,
            'symbol': self.symbol,
            'chargefee': chargefee,
            'trade_pwd': '121851',
            'withdraw_address': address,
            'withdraw_amount': amount,
            'target': 'address'
        }

        result = self.okex_request(api_url=Constants.OKEX_SPOT_WITHDRAW_REST, **params)
        print('withdraw result: {}'.format(result))

        return result.get('result', False)

    def request(self, resource, params, type):
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
        }
        if type == "post":
            temp_params = urllib.parse.urlencode(params)
            res = self.session.post(url=self.base_url + resource, data=temp_params, timeout=self.timeout, headers=headers)
        elif type == "get":
            res = self.session.get(url=self.base_url + resource, params=params, timeout=self.timeout)
        if res.status_code == 200:
            return res.json()
            #return json.loads(res.content, encoding='utf-8')
        else:
            # print(res)
            logger.exception("request error")
            raise RequestException("status error")

    # 向API发送请求
    def okex_request(self, api_url, **kwargs):

        params = {}
        if api_url is Constants.OKEX_SPOT_DELETE_ORDER_REST:
            order_id = kwargs.get('order_id', None)
            params = {'api_key': self.apikey, 'symbol': self.symbol, 'order_id': order_id}


        elif api_url is Constants.OKEX_SPOT_TRADE_REST:
            params = {'api_key': self.apikey, 'symbol': self.symbol,
                      'type': str(kwargs.get('type'))}
            amount = kwargs.get('amount', None)
            if amount:
                params['amount'] = amount
            price = kwargs.get('price', None)
            if price:
                params['price'] = price

        elif api_url is Constants.OKEX_SPOT_ORDERINFO_REST:
            params = {'api_key': self.apikey, 'symbol': self.symbol,
                      'order_id': str(kwargs.get('order_id'))}

        elif api_url is Constants.OKEX_SPOT_ORDERSINFO_REST:
            params = {'api_key': self.apikey, 'symbol': self.symbol, "type": 1,
                      'order_id': kwargs.get('order_id_query_string')}

        elif api_url is Constants.OKEX_SPOT_USERINFO_REST:
            params = {'api_key': self.apikey}
        elif api_url is Constants.OKEX_SPOT_WITHDRAW_REST:
            params.update(kwargs)

        params['sign'] = self.buildMySign(params, self.apisec)

        print(' param: {}'.format(params))


        res = self.request(api_url, params=params, type='post')
        return res

    def parse_meta(self, meta_code):
        meta_table = {'eth_usdt': ("ETH", "USDT", "eth_usdt"),
                      'eth_usd': ("ETH", "USD", "eth_usd"),
                      'usdt_usd': ("USDT", "USD", "usdt_usd"),
                      'btc_usdt': ("BTC", "USDT", "btc_usdt"),
                      'eth_btc': ("ETH", "BTC", "eth_btc"),
                      'bnb_btc': ('BNB', 'BTC', 'bnb_btc'),
                      'bnb_usdt': ('BNB', 'USDT', 'bnb_usdt'),
                      'ltc_eth': ('LTC', 'ETH', 'ltc_eth'),
                      'ltc_bnb': ('LTC', 'BNB', 'ltc_bnb'),
                      'bcc_usdt': ('BCC', 'USDT', 'bcc_usdt'),
                      'bcc_bnb': ('BCC', 'BNB', 'bcc_bnb'),
                      'bcc_btc': ('BCC', 'BTC', 'bcc_btc'),
                      'ven_bnb': ('VEN', 'BNB', 'ven_bnb'),
                      'bnb_eth': ('BNB', 'ETH', 'bnb_eth'),
                      'ven_eth': ('VEN', 'ETH', 'ven_eth'),
                      'bcc_eth': ('BCC', 'ETH', 'bcc_eth'),
                      'ltc_btc': ('LTC', 'BTC', 'ltc_btc'),
                      'ltc_usdt': ('LTC', 'USDT', 'ltc_usdt'),
                      'eos_eth': ('EOS', 'ETH', 'eos_eth'),
                      'eos_btc': ('EOS', 'BTC', 'eos_btc'),
                      'bch_eth': ('BCH', 'ETH', 'bch_eth'),
                      'bch_btc': ('BCH', 'BTC', 'bch_btc'),
                      }
        return meta_table[meta_code]


def test_buy_eth_use_usdt():
    os.environ[Constants.DQUANT_ENV] = "dev"
    ok = OkexSpotRest("eth_usdt")
    # print(ok.getDepth())
    # print(ok.getAccount(coin=['eth', 'btc', 'usdt', 'ltc']))
    #print(ok.sell(0.01))
    print(ok.getAccount(coin=['eth', 'btc', 'usdt']))
    bid0 = ok.getDepth()['bids'][0]['price']
    res = ok.buy(amount=0.01, price=bid0)
    print(res)
    while True:
        order = ok.getOrder(res['order_id'])
        print(order)
        print(ok.getAccount(coin=['eth', 'btc', 'usdt']))
        time.sleep(1)
    #print(ok.buy(amount=0.01, price=600))
    #print(ok.get_active_orders())
    #print(ok.cancel_active_orders())
    #print(ok.get_active_orders())
    # print(ok.deleteOrder(order_id=46451257))
    #print(ok.getOrder(order_id=60070846))
    # print(ok.getOrder())
    # while True:
    #     print(ba.getAccount(coin=["ETH", "BTC", "USDT"]))
    #     time.sleep(1)


    # print(ba.sell(volume=0.01))
    # {'symbol': 'ETHUSDT', 'orderId': 7234294, 'clientOrderId': 'uml0C3DduIhTS0Xkojdrrr', 'transactTime': 1513650349325, 'price': '0.00000000', 'origQty': '0.01000000', 'executedQty': '0.01000000', 'status': 'FILLED', 'timeInForce': 'GTC', 'type': 'MARKET', 'side': 'SELL'}
    # print(ba.getOrder('9916743'))
    # print(ba.getOrder())
    # print ba.getOrder(9916426)
    # print ba.getAccount(coin=["ETH","BTC","USDT"])
    # print(ba.buy(volume=0.01))
    # print ba.getAccount(coin=["ETH","BTC","USDT"])
    # print(ba.getOrder(22888891))
    # print(ba.deleteOrder(22888891))

def test_buy_eth_use_btc():
    os.environ[Constants.DQUANT_ENV] = "dev"
    ok = OkexSpotRest("usdt_usd")
    #print(ok.get_active_orders())
    # print(ok.buy_step_by_step(10000, 10))
    # print(ok.getDepth())
    #print(ok.getAccount())
    ok.withdraw('usdt', '1Ba3Fms4UD6kJD8XVxR2Lfut9scVBZCZem', 100, 2)

if __name__ == "__main__":
    #test_buy_eth_use_usdt()
    test_buy_eth_use_btc()