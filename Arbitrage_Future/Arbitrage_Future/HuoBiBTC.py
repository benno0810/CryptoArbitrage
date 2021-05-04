# -*- coding: utf-8 -*-
import base64
import datetime
import hashlib
import hmac
import json
import requests
import sys
import urllib
import urlparse
import time
import socket
socket.setdefaulttimeout(3.0)
HUOBI_SERVICE_API="https://api.huobi.com/apiv3"

BUY = "buy"
BUY_MARKET = "buy_market"
CANCEL_ORDER = "cancel_order"
ACCOUNT_INFO = "get_account_info"
NEW_DEAL_ORDERS = "get_new_deal_orders"
ORDER_ID_BY_TRADE_ID = "get_order_id_by_trade_id"
GET_ORDERS = "get_orders"
ORDER_INFO = "order_info"
SELL = "sell"
SELL_MARKET = "sell_market"
BTC_TYPE = 1

delay_time = 0.1
class HuoBiBTC:

    def __init__(self,config,name="HuoBi",currency=BTC_TYPE):
        self.currency = currency
        self.access_key = config[name]["access_key"]
        self.secret_key = config[name]["secret_key"]
        # print self.access_key,self.secret_key
        # self.start_timeout = int(config[name]["start_time_out"])
        self.session = requests.Session()
    def get_account(self,acct_id=None):
        """
        :param acct_id
        :return:
        """
        try:
            timestamp = long(time.time())
            params = {"access_key": self.access_key, "secret_key": self.secret_key, "created": timestamp, "method": ACCOUNT_INFO}
            sign = self.signature(params)
            params['sign'] = sign
            del params['secret_key']
            payload = urllib.urlencode(params)
            r = requests.post(HUOBI_SERVICE_API, params=payload)
            if r.status_code == 200:
                data = r.json()
                return data
            else:
                return None
        except Exception, ex:
            self.error("get single account",ex)
            return None
    def getK(self,period = "1min"):
        try:
            """
            :param symbol: 可选值：{ ethcny }
            :param period: 可选值：{1min, 5min, 15min, 30min, 60min, 1day, 1mon, 1week, 1year }
            :param long_polling: 可选值： { true, false }
            :return:
            """
            params = {'symbol': self.currency,
                      'period': period,
                      "length":500}

            url = MARKET_URL + '/market/kline'
            return self.http_get_request(url, params)
        except Exception, ex:
            self.error("get k",ex)
            return None
    # 下单
    def buy(self,volume, price=-1):
        try:
            """

            :param amount:
            :param source:
            :param symbol:
            :param _type: 可选值 {buy-market：市价买, sell-market：市价卖, buy-limit：限价买, sell-limit：限价卖}
            :param price:
            :return:
            """
            timestamp = long(time.time())
            params = {"access_key": ACCESS_KEY, "secret_key": self.secret_key, "created": timestamp, "coin_type": self.currency,
                      "amount": amount}
            if price<0:
                params["method"] =BUY_MARKET
            else:
                params["price"] = price
                params["method"] = BUY
            sign = self.signature(params)
            params['sign'] = sign
            del params['secret_key']
            payload = urllib.urlencode(params)
            r = requests.post(HUOBI_SERVICE_API, params=payload)
            if r.status_code == 200:
                data = r.json()
                return data
            else:
                return None
        except Exception, ex:
            self.error("buy order",ex)
            return None
    def sell(self,volume,price=-1):
        try:
            timestamp = long(time.time())

            params = {"access_key": self.access_key, "secret_key": self.secret_key, "created": timestamp,
                      "coin_type": self.currency, "amount": amount}
            if price<0:
                params["method"] = SELL_MARKET
            else:
                params["price"] = price
                params["method"] = SELL
            sign = self.signature(params)
            params['sign'] = sign
            del params['secret_key']

            payload = urllib.urlencode(params)
            r = requests.post(HUOBI_SERVICE_API, params=payload)
            if r.status_code == 200:
                data = r.json()
                return data
            else:
                return None
        except Exception, ex:
            self.error("sell order",ex)
            return None

    # 撤销订单
    def deleteOrder(self,order_id):
        try:
            timestamp = long(time.time())
            params = {"access_key": ACCESS_KEY, "secret_key": self.secret_key, "created": timestamp, "coin_type": self.currency,
                      "id": id, "method": CANCEL_ORDER}
            sign = self.signature(params)
            params['sign'] = sign
            del params['secret_key']

            payload = urllib.urlencode(params)
            r = requests.post(HUOBI_SERVICE_API, params=payload)
            if r.status_code == 200:
                data = r.json()
                return data
            else:
                return None
        except Exception, ex:
            self.error("cancel order",ex)
            return None

    # 查询某个订单
    def getOrder(self,order_id):
        try:
            timestamp = long(time.time())
            params = {"access_key": ACCESS_KEY, "secret_key": self.secret_key, "created": timestamp, "coin_type": self.currency,
                      "method": ORDER_INFO, "id": id}
            sign = self.signature(params)
            params['sign'] = sign
            del params['secret_key']

            payload = urllib.urlencode(params)
            r = requests.post(HUOBI_SERVICE_API, params=payload)
            if r.status_code == 200:
                data = r.json()
                return data
            else:
                return None
        except Exception, ex:
            self.error("get order",ex)
            return None
    def getDepth(self,size=30, long_polling=None):
        """
        :param symbol: 可选值：{ ethcny }
        :param type: 可选值：{ percent10, step0, step1, step2, step3, step4, step5 }
        :param long_polling: 可选值： { true, false }
        :return:
        """
        try:
            url = "http://api.huobi.com/staticmarket/depth_btc_%d.js"%size
            js = self.http_get_request_data(url,{})
            return js
        except Exception, ex:
            self.error("getDepth",ex)
            return None
    def error(self,func,err):
        time.sleep(delay_time)
        print >> sys.stderr, "HuoBi\t",func," error,", err
    def http_get_request(self,url, params, add_to_headers=None):
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
        }
        if add_to_headers:
            headers.update(add_to_headers)
        postdata = urllib.urlencode(params)
        # print postdata
        # print url+"?"+postdata
        response = self.session.get(url+"?"+postdata, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception("httpGet failed, detail is:%s" % response.text)
    def http_get_request_data(self,url, params, add_to_headers=None):
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
        }
        if add_to_headers:
            headers.update(add_to_headers)
        postdata = urllib.urlencode(params)
        # print postdata
        # print url+"?"+postdata
        response = self.session.get(url,data=postdata, headers=headers, timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception("httpGet failed, detail is:%d %s" % (response.status_code,response.text))


    def http_post_request(self,url, params, add_to_headers=None):
        headers = {
            "Accept": "application/json",
            'Content-Type': 'application/json'
        }
        if add_to_headers:
            headers.update(add_to_headers)
        postdata = json.dumps(params)
        response = requests.post(url, postdata, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception("httpPost failed, detail is:%d %s" % (response.status_code,response.text))


    def api_key_get(self,params, request_path):
        method = 'GET'
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        params = {'AccessKeyId': self.access_key,
                  'SignatureMethod': 'HmacSHA256',
                  'SignatureVersion': '2',
                  'Timestamp': timestamp}

        host_url = TRADE_URL
        host_name = urlparse.urlparse(host_url).hostname
        host_name = host_name.lower()
        params['Signature'] = self.createSign(params, method, host_name, request_path, self.secret_key)
        url = host_url + request_path
        return self.http_get_request(url, params)


    def api_key_post(self,params, request_path):
        method = 'POST'
        timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        params_to_sign = {'AccessKeyId': self.access_key,
                          'SignatureMethod': 'HmacSHA256',
                          'SignatureVersion': '2',
                          'Timestamp': timestamp}

        host_url = TRADE_URL
        host_name = urlparse.urlparse(host_url).hostname
        host_name = host_name.lower()
        params_to_sign['Signature'] = self.createSign(params_to_sign, method, host_name, request_path, self.secret_key)
        url = host_url + request_path + '?' + urllib.urlencode(params_to_sign)
        return self.http_post_request(url, params)

    def signature(self,params):
        params = sorted(params.iteritems(), key=lambda d: d[0], reverse=False)
        message = urllib.urlencode(params)
        m = hashlib.md5()
        m.update(message)
        m.digest()
        sig = m.hexdigest()
        return sig


    def createSign(self,pParams, method, host_url, request_path, secret_key):
        sorted_params = sorted(pParams.items(), key=lambda d: d[0], reverse=False)
        encode_params = urllib.urlencode(sorted_params)
        payload = [method, host_url, request_path, encode_params]
        payload = '\n'.join(payload)
        # print(payload)
        payload = payload.encode(encoding='UTF8')
        secret_key = secret_key.encode(encoding='UTF8')
        digest = hmac.new(secret_key, payload, digestmod=hashlib.sha256).digest()
        signature = base64.b64encode(digest)
        signature = signature.decode()
        return signature