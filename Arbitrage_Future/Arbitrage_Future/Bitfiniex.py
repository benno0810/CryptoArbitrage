import urllib
import urllib2
import json
import time
import hmac,hashlib
import requests
import sys
import base64
API_URL = 'https://api.bitfinex.com/v1'
PROTOCOL = "https"
HOST = "api.bitfinex.com"
VERSION = "v1"
# HTTP request timeout in seconds
ORDER = "order/new"
GET_ORDER = "order/status"
DELETE_ORDER="order/cancel"
TIMEOUT = 3.0
BALANCES = "balances"
PATH_SYMBOLS = "symbols"
PATH_TICKER = "ticker/%s"
PATH_TODAY = "today/%s"
PATH_STATS = "stats/%s"
PATH_LENDBOOK = "lendbook/%s"
PATH_ORDERBOOK = "book/%s"
offset_nonce=100000
class BitFiniex:
    def __init__(self,config,currency = "ethbtc",name="Bitfinex"):
        self.access_key = config[name]["access_key"]
        self.secret_key = config[name]["secret_key"]
        # self.btc_address = config[name]["btc_address"]
        # self.eth_address = config[name]["eth_address"]
        # self.btc_thres = float(config[name]["btc_thres"])
        # self.eth_thres = float(config[name]["eth_thres"])
        # self.btc_fetch = float(config[name]["btc_percent"])*self.btc_thres
        # self.eth_fetch = float(config[name]["eth_percent"])*self.eth_thres
        self.currency = currency
    def getDepth(self,limit_bids=50,limit_asks=50,group = None):

        try:
            params = {}
            if limit_bids!=None:
                params["limit_bids"] = limit_bids
            if limit_asks!=None:
                params["limit_asks"] = limit_asks
            if group!=None:
                params["group"] = group

            url = API_URL + '/book/'+self.currency
            js = requests.get(url, params,timeout=TIMEOUT)
            return js.json()
        except Exception, ex:
            self.error("getDepth",ex)
            return None

    def getSymbols(self):

        try:
            return self._get(self.url_for(PATH_SYMBOLS))
        except Exception, ex:
            self.error("getSymbols",ex)
            return None
    def server(self):
        return "%s://%s/%s" % (PROTOCOL, HOST, VERSION)

    def url_for(self, path, path_arg=None, parameters=None):

        # build the basic url
        url = "%s/%s" % (self.server(), path)

        # If there is a path_arh, interpolate it into the URL.
        # In this case the path that was provided will need to have string
        # interpolation characters in it, such as PATH_TICKER
        if path_arg:
            url = url % (path_arg)

        # Append any parameters to the URL.
        if parameters:
            url = "%s?%s" % (url, self._build_parameters(parameters))

        return url

    def _build_parameters(self, parameters):
        # sort the keys so we can test easily in Python 3.3 (dicts are not
        # ordered)
        keys = list(parameters.keys())
        keys.sort()

        return '&'.join(["%s=%s" % (k, parameters[k]) for k in keys])
    def error(self,func,err):
        print >> sys.stderr, "Bitfinex\t",func," error,", err
    def _get(self, url):
        return requests.get(url, timeout=TIMEOUT).json()
    def _convert_to_floats(self, data):
        """
        Convert all values in a dict to floats
        """
        for key, value in data.items():
            data[key] = float(value)

        return data
    def get_account(self,tillOK= False):
        while True:
            try:
                params = {'request':'/v1/%s'%BALANCES,
                          'nonce':str(int(round(time.time()*1000))+offset_nonce)
                          }
                # print params["nonce"]
                res =  self._post('https://api.bitfinex.com/v1/%s'%BALANCES,params)
                if res and type(res) == list and len(res)>0 :
                    return res
                else:
                    self.error("get account",res)
                    if tillOK:
                        continue
                    else:
                        return res
            except Exception, ex:
                self.error("get account",ex)
                if tillOK:
                    continue
                else:
                    return None


    def signature(self,payload,params):

        secret_key = self.secret_key.encode(encoding='UTF8')
        digest = hmac.new(secret_key, payload, digestmod=hashlib.sha384).hexdigest()
        # signature = base64.b64encode(digest)
        # signature = signature.decode()
        return digest
    def _post(self, url,params,timeout=TIMEOUT):
        payload = base64.b64encode(json.dumps(params).encode(encoding='UTF8'))
        headers = {
                    "Content-Type":"application/json",
                    "Accept":"application/json",
                     'X-BFX-APIKEY': self.access_key,
                     'X-BFX-PAYLOAD': payload,
                     'X-BFX-SIGNATURE': self.signature(payload,params)
                 }
        return requests.post(url, timeout=timeout,headers=headers,data = json.dumps(params).encode(encoding="UTF8")).json()

    def buy(self,amount, price=-1,type="exchange fill-or-kill"):
        try:

            params = {
                'request': '/v1/%s' % ORDER,
                'nonce': str(int(round(time.time() * 1000))+offset_nonce),
                "type":type,
                "symbol": self.currency,
                "amount":str(amount),
                "side":"buy",
                "ocoorder":False,
                "buy_price_oco":"-1",
                "sell_price_oco":"0"
            }
            if price>0:
                params["price"] = str(price)
            else:
                params["type"] = "market"
            url = "/v1/%s"%ORDER
            return self._post('https://api.bitfinex.com/v1/%s' % ORDER, params,timeout=10)
        except Exception, ex:
            self.error("buy order",ex)
            return None

    def withdraw(self,address,amount,currency = "ethereum",tillOK = False):
        while True:
            try:
                params={
                    "request":"/v1/withdraw",
                    'nonce': str(int(round(time.time() * 1000))+offset_nonce),
                    'withdraw_type':currency,
                    'walletselected':"exchange",
                    "amount":str(amount),
                    "address":address
                }
                res =  self._post('https://api.bitfinex.com/v1/withdraw', params)
                if res!=None and type(res)==list and len(res)>0 and res[0].has_key("status")and res[0]["status"]=="success":
                    return res
                else:
                    self.error("withdraw",res)
                    if tillOK:
                        continue
                    else:
                        return res
            except Exception,ex:
                self.error("withdraw",ex)
                if tillOK:
                    continue
                else:
                    return None
    def sell(self,amount,price=-1,type="exchange fill-or-kill"):
        try:

            params = {
                'request': '/v1/%s' % ORDER,
                'nonce': str(int(round(time.time() * 1000))+offset_nonce),
                "type":type,
                "symbol": self.currency,
                "amount":str(amount),
                "side":"sell",
                "ocoorder":False,
                "buy_price_oco":"-1",
                "sell_price_oco":"0"
            }
            if price>0:
                params["price"] = str(price)
            else:
                params["type"] = "market"
            url = "/v1/%s"%ORDER
            return self._post('https://api.bitfinex.com/v1/%s' % ORDER, params,timeout=10)
        except Exception, ex:
            self.error("sell order",ex)
            return None



    def deleteOrder(self,order_id):
        try:

            params = {
                'request': '/v1/%s' % DELETE_ORDER,
                'nonce': str(int(round(time.time() * 1000))+offset_nonce),
                "order_id":order_id
            }
            return self._post('https://api.bitfinex.com/v1/%s' % DELETE_ORDER, params)
        except Exception, ex:
            self.error("delete order",ex)
            return None

    def getOrder(self,order_id,tillOK=False):
        while True:
            try:
                params = {
                    'request': '/v1/%s' % GET_ORDER,
                    'nonce': str(int(round(time.time() * 1000))+offset_nonce),
                    "order_id":order_id
                }
                res = self._post('https://api.bitfinex.com/v1/%s' % GET_ORDER, params)
                if res.has_key("message"):
                    self.error("get order",res)
                    if tillOK:
                        continue
                return res
            except Exception, ex:
                self.error("get order",ex)
                if tillOK:
                    continue
                else:
                    return None

    def error(self,func,err):
        print >> sys.stderr, "Bitfiniex:\t",func," error,", err

