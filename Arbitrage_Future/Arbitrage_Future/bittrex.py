"""
   See https://bittrex.com/Home/Api
"""
import time
import hmac
import hashlib
import sys
try:
    from urllib import urlencode
    from urlparse import urljoin
except ImportError:
    from urllib.parse import urlencode
    from urllib.parse import urljoin
import requests

api_address = r"https://bittrex.com/home/api"
BUY_ORDERBOOK = 'buy'
SELL_ORDERBOOK = 'sell'
BOTH_ORDERBOOK = 'both'

BASE_URL = 'https://bittrex.com/api/v1.1/%s/'

MARKET_SET = {'getopenorders', 'cancel', 'sellmarket', 'selllimit', 'buymarket', 'buylimit'}

ACCOUNT_SET = {'getbalances', 'getbalance', 'getdepositaddress', 'withdraw', 'getorderhistory','getorder'}


class Bittrex(object):
    """
    Used for requesting Bittrex with API key and API secret
    """
    def __init__(self, config,name = "Bittrex",currency = "BTC-ETH"):

        self.api_key = config[name]["access_key"]
        self.api_secret = config[name]["secret_key"]
        self.currency = currency

    def api_query(self, method, options=None,timeout=3.0):
        """
        Queries Bittrex with given method and options

        :param method: Query method for getting info
        :type method: str

        :param options: Extra options for query
        :type options: dict

        :return: JSON response from Bittrex
        :rtype : dict
        """
        if not options:
            options = {}
        nonce = str(int(time.time() * 1000))
        method_set = 'public'

        if method in MARKET_SET:
            method_set = 'market'
        elif method in ACCOUNT_SET:
            method_set = 'account'

        request_url = (BASE_URL % method_set) + method + '?'

        if method_set != 'public':
            request_url += 'apikey=' + self.api_key + "&nonce=" + nonce + '&'

        request_url += urlencode(options)

        return requests.get(
            request_url,
            headers={"apisign": hmac.new(self.api_secret.encode(), request_url.encode(), hashlib.sha512).hexdigest()},
            timeout = timeout
        ).json()

    def get_markets(self):
        """
        Used to get the open and available trading markets
        at Bittrex along with other meta data.

        :return: Available market info in JSON
        :rtype : dict
        """
        return self.api_query('getmarkets')

    def get_currencies(self):
        """
        Used to get all supported currencies at Bittrex
        along with other meta data.

        :return: Supported currencies info in JSON
        :rtype : dict
        """
        return self.api_query('getcurrencies')

    def get_ticker(self, market):
        """
        Used to get the current tick values for a market.

        :param market: String literal for the market (ex: BTC-LTC)
        :type market: str

        :return: Current values for given market in JSON
        :rtype : dict
        """
        return self.api_query('getticker', {'market': market})

    def get_market_summaries(self):
        """
        Used to get the last 24 hour summary of all active exchanges

        :return: Summaries of active exchanges in JSON
        :rtype : dict
        """
        return self.api_query('getmarketsummaries')

    def getDepth(self,  depth=10,tillOK= False):
        while True:
            try:
                res = self.api_query('getorderbook', {'market': self.currency, 'type': BOTH_ORDERBOOK, 'depth': depth})
                if res and res.has_key("success") and res["success"]and res["result"]["buy"]and res["result"]["sell"]:
                    return res
                else:
                    if tillOK:
                        self.error("getDepth",res)
                        # print res
                        continue
                    return res
            except Exception,ex:
                self.error("getDepth",ex)
                if tillOK:
                    continue
                else:
                    return None
    def error(self,func,err):
        print >> sys.stderr, "Bittrex\t",func," error,", err


    def get_market_history(self, market, count):
        """
        Used to retrieve the latest trades that have occurred for a
        specific market.

        /market/getmarkethistory

        :param market: String literal for the market (ex: BTC-LTC)
        :type market: str

        :param count: Number between 1-100 for the number of entries to return (default = 20)
        :type count: int

        :return: Market history in JSON
        :rtype : dict
        """
        return self.api_query('getmarkethistory', {'market': market, 'count': count})

    def buy(self, amount,rate=-1,tillOK=False):
        """
        Used to place a buy order in a specific market. Use buymarket to
        place market orders. Make sure you have the proper permissions
        set on your API keys for this call to work

        /market/buymarket

        :param market: String literal for the market (ex: BTC-LTC)
        :type market: str

        :param quantity: The amount to purchase
        :type quantity: float

        :param rate: The rate at which to place the order.
            This is not needed for market orders
        :type rate: float

        :return:
        :rtype : dict
        """
        while True:
            try:
                if rate<0:
                    res = self.api_query('buymarket', {'market': self.currency, 'quantity': amount},timeout=10)
                else:
                    res = self.api_query('buylimit', {'market': self.currency, 'quantity': amount, 'rate': rate},timeout=10)
                if res and res.has_key("success") and res["success"]:
                    return res
                else:
                    if tillOK:
                        self.error("buy",res)
                        continue
                    else:
                        return res
            except Exception,ex:
                self.error("buy",ex)
                if tillOK:
                    continue
                else:
                    return None

    def sell(self, amount, rate=-1,tillOK = False):
        """
        Used to place a sell order in a specific market. Use sellmarket to place
        market orders. Make sure you have the proper permissions set on your
        API keys for this call to work

        /market/sellmarket

        :param market: String literal for the market (ex: BTC-LTC)
        :type market: str

        :param quantity: The amount to purchase
        :type quantity: float

        :param rate: The rate at which to place the order.
            This is not needed for market orders
        :type rate: float

        :return:
        :rtype : dict
        """
        while True:
            try:
                if rate<0:
                    res = self.api_query('sellmarket', {'market': self.currency, 'quantity': amount},timeout=10)
                else:
                    res = self.api_query('selllimit', {'market': self.currency, 'quantity': amount, 'rate': rate},timeout=10)
                if res and res.has_key("success") and res["success"]:
                    return res
                else:
                    if tillOK:
                        self.error("sell",res)
                        continue
                    else:
                        return res
            except Exception,ex:
                self.error("sell",ex)
                if tillOK:
                    continue
                else:
                    return None
    def deleteOrder(self, uuid,tillOK=False):
        """
        Used to cancel a buy or sell order

        /market/cancel

        :param uuid: uuid of buy or sell order
        :type uuid: str

        :return:
        :rtype : dict
        """
        while True:
            try:
                res = self.api_query('cancel', {'uuid': uuid})
                if res and res.has_key("success") and (res["success"] or res["message"]=="ORDER_NOT_OPEN"):
                    return res
                else:
                    if tillOK:
                        self.error("deleteOrder",res)
                        continue
                    else:
                        return res
            except Exception,ex:
                self.error("deleteOrder",ex)
                if tillOK:
                    continue
                else:
                    return None

    def getOrder(self, uuid,tillOK=False):
        """
        Used to cancel a buy or sell order

        /market/cancel

        :param uuid: uuid of buy or sell order
        :type uuid: str

        :return:
        :rtype : dict
        """
        while True:
            try:
                res = self.api_query('getorder', {'uuid': uuid})
                if res and res.has_key("success") and res["success"]:
                    return res
                else:
                    if tillOK:
                        self.error("getorder",res)
                        continue
                    else:
                        return res
            except Exception,ex:
                self.error("getorder",ex)
                if tillOK:
                    continue
                else:
                    return None
    def get_open_orders(self, market):
        """
        Get all orders that you currently have opened. A specific market can be requested

        /market/getopenorders

        :param market: String literal for the market (ie. BTC-LTC)
        :type market: str

        :return: Open orders info in JSON
        :rtype : dict
        """
        return self.api_query('getopenorders', {'market': market})

    def get_account(self,tillOK = False):
        """
        Used to retrieve all balances from your account

        /account/getbalances

        :return: Balances info in JSON
        :rtype : dict
        """

        while True:
            try:
                res = self.api_query('getbalances', {})
                if res and res.has_key("success") and res["success"]:
                    return res
                else:
                    if tillOK:
                        self.error("getAccount",res)
                        continue
                    else:
                        return res
            except Exception,ex:
                self.error("getAccount",ex)
                if tillOK:
                    continue
                else:
                    return None

    def get_balance(self, currency):
        """
        Used to retrieve the balance from your account for a specific currency

        /account/getbalance

        :param currency: String literal for the currency (ex: LTC)
        :type currency: str

        :return: Balance info in JSON
        :rtype : dict
        """
        return self.api_query('getbalance', {'currency': currency})

    def get_deposit_address(self, currency):
        """
        Used to generate or retrieve an address for a specific currency

        /account/getdepositaddress

        :param currency: String literal for the currency (ie. BTC)
        :type currency: str

        :return: Address info in JSON
        :rtype : dict
        """
        return self.api_query('getdepositaddress', {'currency': currency})

    def withdraw(self, currency, quantity, address):
        """
        Used to withdraw funds from your account

        /account/withdraw

        :param currency: String literal for the currency (ie. BTC)
        :type currency: str

        :param quantity: The quantity of coins to withdraw
        :type quantity: float

        :param address: The address where to send the funds.
        :type address: str

        :return:
        :rtype : dict
        """
        return self.api_query('withdraw', {'currency': currency, 'quantity': quantity, 'address': address})

    def get_order_history(self, market, count):
        """
        Used to reterieve order trade history of account

        /account/getorderhistory

        :param market: optional a string literal for the market (ie. BTC-LTC). If ommited, will return for all markets
        :type market: str

        :param count: optional 	the number of records to return
        :type count: int

        :return: order history in JSON
        :rtype : dict

        """
        return self.api_query('getorderhistory', {'market':market, 'count': count})
