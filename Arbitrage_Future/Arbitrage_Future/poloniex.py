import urllib
import urllib2
import json
import time
import hmac,hashlib
import requests
import socket
import sys
socket.setdefaulttimeout(30.0)
def createTimeStamp(datestr, format="%Y-%m-%d %H:%M:%S"):
    return time.mktime(time.strptime(datestr, format))

class poloniex:
    def __init__(self, config,name = "Poloniex",currency_pair = "BTC_ETH"):
        self.currency_pair = currency_pair
        self.APIKey = str(config[name]["access_key"])
        self.Secret = str(config[name]["secret_key"])
        self.session = requests.Session()

    def post_process(self, before):
        after = before

        # Add timestamps if there isnt one but is a datetime
        if('return' in after):
            if(isinstance(after['return'], list)):
                for x in xrange(0, len(after['return'])):
                    if(isinstance(after['return'][x], dict)):
                        if('datetime' in after['return'][x] and 'timestamp' not in after['return'][x]):
                            after['return'][x]['timestamp'] = float(createTimeStamp(after['return'][x]['datetime']))

        return after

    def api_query(self, command, req={}):

        if(command == "returnTicker" or command == "return24Volume"):
            ret = self.session.get('https://poloniex.com/public?command=' + command)
            return ret.json()
        elif(command == "returnOrderBook"):
            ret = self.session.get('https://poloniex.com/public?command=' + command + '&currencyPair=' + str(req['currencyPair']))
            return ret.json()
        elif(command == "returnMarketTradeHistory"):
            ret = self.session.get('https://poloniex.com/public?command=' + "returnTradeHistory" + '&currencyPair=' + str(req['currencyPair']))
            return ret.json()
        else:
            req['command'] = command
            req['nonce'] = int(time.time()*1000)
            post_data = urllib.urlencode(req)

            sign = hmac.new(self.Secret, post_data, hashlib.sha512).hexdigest()
            headers = {
                'Sign': sign,
                'Key': self.APIKey
            }

            ret = urllib2.urlopen(urllib2.Request('https://poloniex.com/tradingApi', post_data, headers))
            jsonRet = json.loads(ret.read())
            return self.post_process(jsonRet)


    def returnTicker(self):
        try:
            return self.api_query("returnTicker")
        except Exception,ex:
            self.error("returnTicker",ex)
            return None

    def return24Volume(self):
        return self.api_query("return24Volume")

    def getDepth (self):
        try:
            return self.api_query("returnOrderBook", {'currencyPair': self.currency_pair})
        except Exception,ex:
            self.error("getDepth",ex)
            return None

    def returnMarketTradeHistory (self):
        try:
            return self.api_query("returnMarketTradeHistory", {'currencyPair': self.currency_pair})
        except Exception,ex:
            self.error("returnMarketTradeHistory",ex)
            return None


    # Returns all of your balances.
    # Outputs:
    # {"BTC":"0.59098578","LTC":"3.31117268", ... }
    def get_account(self):
        try:
            return self.api_query('returnBalances')
        except Exception,ex:
            self.error("get_account",ex)
            return None

    # Returns your open orders for a given market, specified by the "currencyPair" POST parameter, e.g. "BTC_XCP"
    # Inputs:
    # currencyPair  The currency pair e.g. "BTC_XCP"
    # Outputs:
    # orderNumber   The order number
    # type          sell or buy
    # rate          Price the order is selling or buying at
    # Amount        Quantity of order
    # total         Total value of order (price * quantity)
    def returnOpenOrders(self):
        try:
            return self.api_query('returnOpenOrders',{"currencyPair":self.currency_pair})
        except Exception,ex:
            self.error("returnOpenOrders",ex)
            return None

    def getOrder(self,order_id):
        try:
            return self.api_query('returnOrderTrades',{"orderNumber":order_id})
        except Exception,ex:
            self.error("getOrder",ex)
            return None


    # Returns your trade history for a given market, specified by the "currencyPair" POST parameter
    # Inputs:
    # currencyPair  The currency pair e.g. "BTC_XCP"
    # Outputs:
    # date          Date in the form: "2014-02-19 03:44:59"
    # rate          Price the order is selling or buying at
    # amount        Quantity of order
    # total         Total value of order (price * quantity)
    # type          sell or buy
    def returnTradeHistory(self,currencyPair):
        try:
            return self.api_query('returnTradeHistory',{"currencyPair":currencyPair})
        except Exception,ex:
            self.error("returnTradeHistory",ex)
            return None

    # Places a buy order in a given market. Required POST parameters are "currencyPair", "rate", and "amount". If successful, the method will return the order number.
    # Inputs:
    # currencyPair  The curreny pair
    # rate          price the order is buying at
    # amount        Amount of coins to buy
    # Outputs:
    # orderNumber   The order number
    def buyFillorKill(self,rate,amount):
        try:
            return self.api_query('buy',{"currencyPair":self.currency_pair,"rate":rate,"amount":amount,"fillOrKill":1})
        except Exception,ex:
            self.error("buyFillorKill",ex)
            return None

    def buy(self,rate,amount):
        try:
            return self.api_query('buy',{"currencyPair":self.currency_pair,"rate":rate,"amount":amount})
        except Exception,ex:
            self.error("buy",ex)
            return None

    # Places a sell order in a given market. Required POST parameters are "currencyPair", "rate", and "amount". If successful, the method will return the order number.
    # Inputs:
    # currencyPair  The curreny pair
    # rate          price the order is selling at
    # amount        Amount of coins to sell
    # Outputs:
    # orderNumber   The order number
    def sellFillorKill(self,rate,amount):
        try:
            return self.api_query('sell',{"currencyPair":self.currency_pair,"rate":rate,"amount":amount,"fillOrKill":1})
        except Exception,ex:
            self.error("sellFillorKill",ex)
            return None
    def sell(self,rate,amount):
        try:
            return self.api_query('sell',{"currencyPair":self.currency_pair,"rate":rate,"amount":amount})
        except Exception,ex:
            self.error("sell",ex)
            return None

    # Cancels an order you have placed in a given market. Required POST parameters are "currencyPair" and "orderNumber".
    # Inputs:
    # currencyPair  The curreny pair
    # orderNumber   The order number to cancel
    # Outputs:
    # succes        1 or 0
    def cancel(self,orderNumber):
        try:
            return self.api_query('cancelOrder',{"currencyPair":self.currency_pair,"orderNumber":orderNumber})
        except Exception,ex:
            self.error("cancel",ex)
            return None

    # Immediately places a withdrawal for a given currency, with no email confirmation. In order to use this method, the withdrawal privilege must be enabled for your API key. Required POST parameters are "currency", "amount", and "address". Sample output: {"response":"Withdrew 2398 NXT."}
    # Inputs:
    # currency      The currency to withdraw
    # amount        The amount of this coin to withdraw
    # address       The withdrawal address
    # Outputs:
    # response      Text containing message about the withdrawal
    def withdraw(self, currency, amount, address):
        return self.api_query('withdraw',{"currency":currency, "amount":amount, "address":address})

    def error(self,func,err):
        time.sleep(0.1)
        print >> sys.stderr, "poloniex:\t",func," error,", err
