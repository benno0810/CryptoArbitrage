import hmac

import json, urllib2, hashlib,struct,sha,time
import sys
from collections import OrderedDict
import requests
requests.adapters.DEFAULT_RETRIES = 5
delay_time = 0.1
api_address=r"https://www.chbtc.com/i/developer"
class CNBTC:
    def __init__(self, config,currency = "eth_cny"):
        self.currency = currency
        self.mykey = config["CNBTC"]["access_key"]
        self.mysecret = config["CNBTC"]["secret_key"]
        self.baseAPIUrl = "http://api.chbtc.com/data/v1/"
        self.baseTradeUrl = "https://trade.chbtc.com/api/"
        self.start_timeout = int(config["CNBTC"]["start_time_out"])
        self.session = requests.Session()

    def __fill(self, value, lenght, fillByte):
        if len(value) >= lenght:
            return value
        else:
            fillSize = lenght - len(value)
        return value + chr(fillByte) * fillSize

    def __doXOr(self, s, value):
        slist = list(s)
        for index in xrange(len(slist)):
            slist[index] = chr(ord(slist[index]) ^ value)
        return "".join(slist)

    def __hmacSign(self, aValue, aKey):
        keyb = struct.pack("%ds" % len(aKey), aKey.encode("utf8"))
        value = struct.pack("%ds" % len(aValue), aValue.encode("utf8"))
        k_ipad = self.__doXOr(keyb, 0x36)
        k_opad = self.__doXOr(keyb, 0x5c)
        k_ipad = self.__fill(k_ipad, 64, 54)
        k_opad = self.__fill(k_opad, 64, 92)
        m = hashlib.md5()
        m.update(k_ipad)
        m.update(value)
        dg = m.digest()

        m = hashlib.md5()
        m.update(k_opad)
        subStr = dg[0:16]
        m.update(subStr)
        dg = m.hexdigest()
        return dg

    def __digest(self, aValue):
        value = struct.pack("%ds" % len(aValue), aValue.encode("utf8"))
        h = sha.new()
        h.update(value)
        dg = h.hexdigest()
        return dg

    def genReqTime(self):
        return str((int)(time.time() * 1000))


    def genSig(self, query):
        SHA_secret = self.__digest(self.mysecret)
        return self.__hmacSign(query, SHA_secret)

    def genUrl(self, base_url, uri, params=OrderedDict()):
        query = ""
        # params.update({"accesskey":self.mykey})
        for key in params.keys():
            query = "%s&%s=%s" % (query, key, params[key]) if len(query) != 0 else "%s=%s" % (key, params[key])
        sig = self.genSig(query)
        if len(query) > 0:
            query += "&"
        query += 'sign=%s&reqTime=%s' % (sig, self.genReqTime())
        return base_url+uri + "?" + query
    def getK(self,since,period="1min",size=1000):
        try:
            uri = "kline"
            params = OrderedDict()
            ####order can not change
            params["currency"] = self.currency
            params["type"] = period
            params["since"] = str(since)
            params["size"] = str(size)
            # params["merge"] = "0.5"
            res = self.session.get(self.genUrl(self.baseAPIUrl,uri, params))
            return json.loads(res.text)
        except Exception, ex:
            self.error("getDepth",ex)
            return None
    def getDepth(self, size=10):
        try:
            uri = "depth"
            params = OrderedDict()
            ####order can not change
            params["currency"] = self.currency
            params["size"] = str(size)
            # params["merge"] = "0.5"
            res = self.session.get(self.genUrl(self.baseAPIUrl,uri, params),timeout=self.start_timeout)
            return json.loads(res.text)
        except Exception, ex:
            self.error("getDepth",ex)
            return None
    def get_account(self):
        try:
            uri = "getAccountInfo"
            params =OrderedDict()
            params["method"]="getAccountInfo"
            params["accesskey"]=self.mykey
            res = self.session.get(self.genUrl(self.baseTradeUrl,uri,params),timeout=self.start_timeout)
            return json.loads(res.text)
        except Exception, ex:
            self.error("get account",ex)
            return None
    def buy(self,volume,price):
        try:
            params=OrderedDict()
            uri = "order"
            params["method"] = "order"
            params["accesskey"] = self.mykey
            params["price"]=str(price)
            params["amount"] = str(volume)
            params["tradeType"]="1"
            params["currency"]=self.currency
            res = self.session.post(self.genUrl(self.baseTradeUrl,uri,params),timeout=self.start_timeout+5)
            js = json.loads(res.text)
            #print js["message"]
            return js
        except Exception, ex:
            self.error("buy",ex)
            return None
    def sell(self,volume,price):
        try:
            params=OrderedDict()
            uri = "order"
            params["method"] = "order"
            params["accesskey"] = self.mykey
            params["price"]=str(price)
            params["amount"] = str(volume)
            params["tradeType"]="0"
            params["currency"]=self.currency
            res = self.session.post(self.genUrl(self.baseTradeUrl,uri,params),timeout=self.start_timeout+5)
            return json.loads(res.text)
        except Exception, ex:
            self.error("sell",ex)
            return None
    def getOrder(self,id):
        try:
            params=OrderedDict()
            uri = "getOrder"
            params["method"] = "getOrder"
            params["accesskey"] = self.mykey
            params["id"] = id
            params["currency"]=self.currency
            res = self.session.get(self.genUrl(self.baseTradeUrl,uri,params),timeout=self.start_timeout)
            js = json.loads(res.text)
            return js
        except Exception, ex:
            self.error("getOrder",ex)
            return None
    def deleteOrder(self,id):
        try:
            params=OrderedDict()
            uri = "cancelOrder"
            params["method"] = "cancelOrder"
            params["accesskey"] = self.mykey
            params["id"] = id
            params["currency"]=self.currency
            res = self.session.get(self.genUrl(self.baseTradeUrl,uri,params),timeout=self.start_timeout)
            js = json.loads(res.text)
            return js
        except Exception, ex:
            self.error("deleteOrder",ex)
            return None
    def error(self,func,err):
        time.sleep(delay_time)
        print >> sys.stderr, "CNBTC\t",func," error,", err


