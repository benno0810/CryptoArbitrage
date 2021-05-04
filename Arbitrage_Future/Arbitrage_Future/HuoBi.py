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
import socket
import sys
socket.setdefaulttimeout(3.0)
# 此处填写APIKEY

# ACCESS_KEY = ""
# SECRET_KEY = ""


# API 请求地址
MARKET_URL = "https://be.huobi.com"
TRADE_URL = "https://be.huobi.com"
import time
delay_time = 0.1
class HuoBi:

    def __init__(self,config,name="HuoBi",currency="ethcny"):
        self.currency = currency
        self.access_key = config[name]["access_key"]
        self.secret_key = config[name]["secret_key"]
        # print self.access_key,self.secret_key
        # self.start_timeout = int(config[name]["start_time_out"])
        self.session = requests.Session()
    def get_accounts(self):
        """
        :return:
        """
        try:
            path = "/v1/account/accounts"
            params = {}
            return self.api_key_get(params, path)
        except Exception, ex:
            self.error("get all accounts",ex)
            return None
    def get_account(self,acct_id=None):
        """
        :param acct_id
        :return:
        """
        try:
            if not acct_id:
                accounts = self.get_accounts()
                # print aacounts

                acct_id = accounts['data'][0]['id'];

            url = "/v1/account/accounts/{0}/balance".format(acct_id)
            params = {"account-id": acct_id}
            return self.api_key_get(params, url)
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
            accounts = self.get_accounts()
            acct_id = accounts['data'][0]['id'];
            _type = "buy-limit"
            params = {"account-id": acct_id,
                      "amount": str(volume),
                      "symbol": self.currency,
                      "source": "api"}
            if price>0:
                params["price"] = "%.2f"%price
                params["type"] = "buy-limit"
            else:
                params["type"] = "buy-market"


            url = "/v1/order/orders"
            return self.api_key_post(params, url)
        except Exception, ex:
            self.error("buy order",ex)
            return None
    def sell(self,volume,price=-1):
        try:
            """

            :param amount:
            :param source:
            :param symbol:
            :param _type: 可选值 {buy-market：市价买, sell-market：市价卖, buy-limit：限价买, sell-limit：限价卖}
            :param price:
            :return:
            """
            accounts = self.get_accounts()
            acct_id = accounts['data'][0]['id'];
            _type = "sell-limit"
            params = {"account-id": acct_id,
                      "amount": str(volume),
                      "symbol": self.currency,
                      "source":"api"}

            if price>0:
                params["price"] = "%.2f"%price
                params["type"] = "sell-limit"
            else:
                params["type"] = "sell-market"


            url = "/v1/order/orders"
            return self.api_key_post(params, url)
        except Exception, ex:
            self.error("sell order",ex)
            return None


    # 执行订单
    def place_order(self,order_id):
        try:
            """

            :param order_id:
            :return:
            """
            params = {}
            url = "/v1/order/orders/{0}/place".format(order_id)
            return self.api_key_post(params, url)
        except Exception, ex:
            self.error("place order",ex)
            return None


    # 撤销订单
    def deleteOrder(self,order_id):
        try:
            """

            :param order_id:
            :return:
            """
            params = {}
            url = "/v1/order/orders/{0}/submitcancel".format(order_id)
            return self.api_key_post(params, url)
        except Exception, ex:
            self.error("cancel order",ex)
            return None

    # 查询某个订单
    def getOrder(self,order_id):
        try:
            """

            :param order_id:
            :return:
            """
            params = {}
            url = "/v1/order/orders/{0}".format(order_id)
            return self.api_key_get(params, url)

        except Exception, ex:
            self.error("get order",ex)
            return None
    def getDepth(self,type="percent10", long_polling=None):
        """
        :param symbol: 可选值：{ ethcny }
        :param type: 可选值：{ percent10, step0, step1, step2, step3, step4, step5 }
        :param long_polling: 可选值： { true, false }
        :return:
        """
        try:
            params = {'symbol': self.currency,
                      'type': type}

            if long_polling:
                params['long-polling'] = long_polling
            url = MARKET_URL + '/market/depth'
            js = self.http_get_request_data(url, params)
            return js
        except Exception, ex:
            self.error("getDepth",ex)
            return None
    def error(self,func,err):
        time.sleep(delay_time)
        print >> sys.stderr, "HuoBi\t",func," error,", err
    def getDepth_BTC(self,size=30, long_polling=None):
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

