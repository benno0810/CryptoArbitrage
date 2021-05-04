import sys

import time

sys.path.append('../../')
import os
import json
import logging

import requests, hashlib
from requests import RequestException
from urllib.parse import urlencode

from dquant.config import cfg
from dquant.constants import Constants
from dquant.markets.market import Market
logger = logging.getLogger(__name__)

class OkexFutureRest(Market):
    def __init__(self, meta_code):
        market_currency, base_currency, symbol, contract_type = self.parse_meta(meta_code)
        super().__init__(market_currency, base_currency, meta_code, cfg.get_float_config(Constants.OKEX_FUTURE_FEE))
        self.apikey = cfg.get_config(Constants.OKEX_FUTURE_APIKEY)
        self.apisec = cfg.get_config(Constants.OKEX_FUTURE_APISEC)
        self.okex_id = cfg.get_config(Constants.OKEX_FUTURE_ID)
        self.contract_type = contract_type
        self.symbol = symbol
        self.base_url = Constants.OKEX_FUTURE_REST_BASE
        self.session = requests.session()
        self.timeout = Constants.OK_HTTP_TIMEOUT

    def get_ticker(self, tillOK=True):
        '''返回值与其他平台的ticker不太一样。所以overide Market中的get_ticker
        '''
        params = {
            'symbol': self.symbol,
            'contract_type': self.contract_type
        }
        while True:
            try:
                res = self.request(Constants.OKEX_FUTURE_TICKER_REST, params, 'get')
                if 'ticker' in res:
                    return res
                elif tillOK:
                    time.sleep(0.5)
                    continue
                else:
                    return None
            except Exception as ex:
                logging.error("OKEXFuture Rest get_ticker: %s, Retry" % ex)
                if tillOK:
                    time.sleep(0.5)
                    continue
                return None

    def get_index(self, tillOK=True):
        '''返回值与其他平台的ticker不太一样。所以overide Market中的get_ticker
        '''
        params = {
            'symbol': self.symbol,
        }
        while True:
            try:
                res = self.request(Constants.OKEX_FUTURE_INDEX_REST, params, 'get')
                if 'future_index' in res:
                    return res
                elif tillOK:
                    time.sleep(0.5)
                    continue
                else:
                    return None
            except Exception as ex:
                logging.error("OKEXFuture Rest get_index: %s, Retry" % ex)
                if tillOK:
                    time.sleep(0.5)
                    continue
                return None

    # 轮询获取depth
    def getDepth(self):
        params = {"symbol": self.symbol,
                  "contract_type": self.contract_type}
        while True:
            try:
                res = self.request(Constants.OKEX_FUTURE_DEPTH_RESOURCE_REST, params, "get")
                list_of_ask = self.okex_depth_format(res,"asks")
                list_of_bid = self.okex_depth_format(res,"bids")
                list_of_ask.reverse()
                return {"asks": list_of_ask, 'bids': list_of_bid}
            except Exception:
                logging.exception("http error")

    @staticmethod
    def okex_depth_format(res, flag):
        '''格式化depth数据'''
        result_list = []
        for ticker in res[flag]:
            result_list.append({
                'price': ticker[0],
                'amount': ticker[1]
            })
        return result_list

    def get_trades(self):

        params = {
            'symbol': self.symbol,
            'contract_type': self.contract_type
        }
        res = self.request(Constants.OKEX_FUTURE_TRADES_REST, params, 'get')
        return res



    def long(self, amount, price=-1, lever_rate='10'):
        '''
        :param amount: 委托数量
        :param price: 价格
        :param lever_rate: 杠杆倍数
        :return:

        type： String
            1:开多   2:开空   3:平多   4:平空

        访问频率 5次/秒
        '''
        res = self.okex_request(price=price, amount=amount, type='1',  api_url=Constants.OKEX_FUTURE_TRADE_REST, lever_rate=lever_rate)
        return res

    def short(self, amount, price=-1, lever_rate='10'):
        res = self.okex_request(price=price, amount=amount, type='2', api_url=Constants.OKEX_FUTURE_TRADE_REST, lever_rate=lever_rate)
        return res

    def closeLong(self, amount, price=-1, lever_rate='10'):
        res = self.okex_request(price=price, amount=amount, type='3', api_url=Constants.OKEX_FUTURE_TRADE_REST, lever_rate=lever_rate)
        return res

    def closeShort(self, amount, price=-1, lever_rate='10'):
        res = self.okex_request(price=price, amount=amount, type='4', api_url=Constants.OKEX_FUTURE_TRADE_REST, lever_rate=lever_rate)
        return res

    def deleteOrder(self, order_id, tillOK=True):
        '''
        :param order_id:
        :return: {'result': True, 'order_id': '14435081666'}
        '''
        while True:
            try:
                res = self.okex_request(order_id=order_id, api_url=Constants.OKEX_FUTURE_DELETE_ORDER_REST)
                if 'result' in res:
                    if res['result'] == True:
                        return res
                if tillOK == True:
                    continue
                else:
                    logging.error(res)
                    break
            except Exception as ex:
                logging.exception("message")
                if tillOK:
                    continue
                return None

    def getAccount(self, coin=[]):
        '''
        :return:{"info": {"btc": {"account_rights": 1,"keep_deposit": 0,"profit_real": 3.33,"profit_unreal": 0,"risk_rate": 10000},"ltc": {"account_rights": 2,"keep_deposit": 2.22,"profit_real": 3.33,"profit_unreal": 2,"risk_rate": 10000},"result": true}
        '''

        res = self.okex_request(api_url=Constants.OKEX_FUTURE_USERINFO_REST)
        if res['result'] is True:
            if coin:
                ret = {}
                for c in coin:
                    if c.lower() in res["info"]:
                        ret[c.lower()] = res["info"][c.lower()]
                return ret
            else:
                return res["info"]

    def getOrder(self, order_id):
        '''
        :return:{"info": {"btc": {"account_rights": 1,"keep_deposit": 0,"profit_real": 3.33,"profit_unreal": 0,"risk_rate": 10000},"ltc": {"account_rights": 2,"keep_deposit": 2.22,"profit_real": 3.33,"profit_unreal": 2,"risk_rate": 10000},"result": true}
        '''

        res = self.okex_request(order_id=order_id, api_url=Constants.OKEX_FUTURE_GET_ORDER_REST)
        pass

    def get_current_and_baocang_price(self):
        '''
        获取当前价格，depth里的max_price，是从ask & bid里选最大值
        :return: {
            'current_price': 1,
            'baocang_price': 2
        }
        '''
        depth = self.getDepth()
        #print('depth asks: ', depth['asks'])
        #print('depth bids: ', depth['bids'])
        tmp = [one['price'] for one in depth['asks']]
        tmp.extend([one['price'] for one in depth['bids']])
        current_price = max(tmp)
        baocang_price = self.getPosition().get('force_liqu_price', -1)  # -1表示没获取到爆仓价格, 0表示没有持仓

        return {'current_price': current_price, 'baocang_price': float(baocang_price.replace(',', ''))}

    def getPosition(self):
        '''
        :return:
         {
            "force_liqu_price": "0.07",
            "holding": [
                {
                    "buy_amount": 1,
                    "buy_available": 0,
                    "buy_price_avg": 422.78,
                    "buy_price_cost": 422.78,
                    "buy_profit_real": -0.00007096,
                    "contract_id": 20141219012,
                    "contract_type": "this_week",
                    "create_date": 1418113356000,
                    "lever_rate": 10,
                    "sell_amount": 0,
                    "sell_available": 0,
                    "sell_price_avg": 0,
                    "sell_price_cost": 0,
                    "sell_profit_real": 0,
                    "symbol": "btc_usd"
                }
            ],
            "result": true
        }
        '''
        res = self.okex_request(api_url=Constants.OKEX_FUTURE_GET_POSITION_REST)
        # print(res)
        if res and "result" in res and res["result"]:
            return res
        else:
            return {}

    def get_active_orders(self, status='1'):
        '''
        :param status: 查询状态 1:未完成的订单 2:已经完成的订单
        :return:{
                  "orders":
                     [
                        {
                            "amount":111,
                            "contract_name":"LTC0815",
                            "create_date":1408076414000,
                            "deal_amount":1,
                            "fee":0,
                            "order_id":106837,
                            "price":1111,
                            "price_avg":0,
                            "status":"0",
                            "symbol":"ltc_usd",
                            "type":"1",
                            "unit_amount":100,
                            "lever_rate":10
                        }
                     ],
                   "result":true
                }
        '''
        status = str(status)
        res = self.okex_request(order_id='-1', status=status, api_url=Constants.OKEX_FUTURE_GET_ORDER_REST)
        if res and "result" in res and res["result"]:
            return res["orders"]
        else:
            return []

    def cancel_all_orders(self):
        try:
            act_orders = self.get_active_orders()
            logger.info("OKEXFuture cancel_all_orders: %s" % act_orders)
            if act_orders:
                for order in act_orders:
                    order_id = order['order_id']
                    self.deleteOrder(order_id)
        except Exception as ex:
            self.error("OKEXFuture cancel_all_orders: %s" % ex)

    def close_all_long_orders(self):
        '''
        :return: {'result': True, 'success': [], 'fail': []}
        '''
        ret = {'result': True, 'success': [], 'fail': [], 'success_amount': 0}
        act_positions = self.getPosition()
        for position in act_positions['holding']:
            try:
                if not (position['symbol'] == self.symbol and position['contract_type'] == self.contract_type):
                    continue
                if position['buy_available']:
                    res = self.closeLong(amount=position['buy_available'], lever_rate=position['lever_rate'])
                    if res and 'result' in res and res['result']:
                        ret['success'].append(res['order_id'])
                        ret['success_amount'] += float(position['buy_available'])
                    else:
                        ret['fail'].append({'long_available': position['buy_available'], 'lever_rate': position['lever_rate'],
                                            'symbol':self.symbol, 'contract_type':self.contract_type})
            except Exception as ex:
                self.error("OKEXFuture close_all_long_orders: %s" % ex)
        logger.info("OKEXFuture close_all_long_orders: %s" % ret)
        return ret


    def close_all_short_orders(self):
        '''
        :return: {'result': True, 'success': [], 'fail': []}
        '''
        ret = {'result': True, 'success': [], 'fail': [], 'success_amount': 0}
        act_positions = self.getPosition()
        for position in act_positions['holding']:
            try:
                if position['sell_available']:
                    res = self.closeShort(amount=position['sell_available'], lever_rate=position['lever_rate'])
                    if res and 'result' in res and res['result']:
                        ret['success'].append(res['order_id'])
                        ret['success_amount'] += float(position['sell_available'])
                    else:
                        ret['fail'].append({'short_available': position['sell_available'], 'lever_rate': position['lever_rate'],
                                            'symbol':self.symbol, 'contract_type':self.contract_type})
            except Exception as ex:
                self.error("OKEXFuture close_all_short_orders: %s" % ex)
        return ret




    # 向API发送请求
    def okex_request(self, api_url, **kwargs):
        '''
        :param price: 默认对手价
        :param amount: 最小为1
        :param type: 1:开多 2:开空 3:平多 4:平空, 'delete_order':取消订单
        :param lever_rate: 杠杆倍数 value:10\20 默认10
        :param match_price: 是否为对手价 0:不是  1:是,当取值为1时,price无效。这里根据price是否为空判断。
        :param contract_type: 合约类型: this_week:当周   next_week:下周   quarter:季度
        :return: {"order_id":986,"result":true}
        '''
        params = {}
        if api_url is Constants.OKEX_FUTURE_DELETE_ORDER_REST:
            order_id = kwargs.get('order_id', None)
            params = {'api_key': self.apikey, 'symbol': self.symbol, 'contract_type': self.contract_type, 'order_id': order_id}
            # params['sign'] = self.buildMySign(params, self.apisec)
            # res = self.request(Constants.OKEX_FUTURE_DELETE_ORDER_REST, params=params, type='post')

        elif api_url is Constants.OKEX_FUTURE_TRADE_REST:
            params = {'api_key': self.apikey, 'symbol': self.symbol, 'contract_type': self.contract_type, 'amount': str(kwargs.get('amount')),
                      'type': str(kwargs.get('type')), 'match_price': '1', 'lever_rate': str(kwargs.get('lever_rate', 10))}
            price = kwargs.get('price', None)
            if price > 0:
                params['price'] = str(price)
                params['match_price'] = '0'

        elif api_url is Constants.OKEX_FUTURE_GET_ORDER_REST:
            order_id = kwargs.get('order_id', None)
            status = kwargs.get('status', None)
            params = {'api_key': self.apikey, 'symbol': self.symbol, 'contract_type': self.contract_type}
            if order_id:
                params['order_id'] = order_id
            if status:
                params['status'] = status
                params['current_page'] = '1'
                params['page_length'] = '50'

        elif api_url is Constants.OKEX_FUTURE_GET_POSITION_REST:
            params = {'api_key': self.apikey, 'symbol': self.symbol, 'contract_type': self.contract_type}
            # _type = kwargs.get('_type', None)
            # params['type'] = _type

        elif api_url is Constants.OKEX_FUTURE_USERINFO_REST:
            params = {'api_key': self.apikey}

        params['sign'] = self.buildMySign(params, self.apisec)
        res = self.request(api_url, params=params, type='post')
        return res

    def request(self, resource, params, type):
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
        }
        if type == "post":
            temp_params = urlencode(params)
            res = self.session.post(url=self.base_url + resource, data=temp_params, timeout=self.timeout,
                                    headers=headers)
        elif type == "get":
            res = self.session.get(url=self.base_url + resource, params=params, timeout=self.timeout)

        if res.status_code == 200:
            return json.loads(res.content.decode())
        else:
            # print(res)
            logging.exception("request error")
            raise RequestException("status error")

    def buildMySign(self, params, secretKey):
        sign = ''
        for key in sorted(params.keys()):
            sign += key + '=' + str(params[key]) + '&'
        data = sign + 'secret_key=' + secretKey
        return hashlib.md5(data.encode("utf8")).hexdigest().upper()

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


def test_btc_usd_this_week():
    os.environ[Constants.DQUANT_ENV] = "dev"
    ok = OkexFutureRest("btc_usd_this_week")
    #print(ok.get_ticker())
    #print(ok.getDepth())
    print(ok.get_trades())
    #print(ok.getAccount())


def test_btc_usd_quarter():
    os.environ[Constants.DQUANT_ENV] = "dev"
    ok = OkexFutureRest("btc_usd_quarter")
    # print(ok.long(amount=1,lever_rate='10'))
    # print(ok.long(amount=1, lever_rate='20'))
    # time.sleep(5)
    print(ok.get_active_orders())
    print(ok.getPosition())
    # print(ok.close_all_long_orders())
    # time.sleep(5)
    # print(ok.get_active_orders())
    # print(ok.getPosition())
    #print(ok.getDepth())
    #print(ok.get_trades())
    #print(ok.getAccount())


def test_others():
    os.environ[Constants.DQUANT_ENV] = "dev"
    ok = OkexFutureRest("btc_usd_this_week")
    print(ok.get_index())


if __name__ == "__main__":

    #test_btc_usd_this_week()
    #test_btc_usd_quarter()
    while True:
        test_others()
        time.sleep(0.5)
