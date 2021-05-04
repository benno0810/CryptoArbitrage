import asyncio
import json
import logging
import os
import datetime
import requests, hmac, hashlib, time
from urllib.parse import urlparse, urlencode
import websockets
from websocket import create_connection

from pymongo import MongoClient

from dquant.config import cfg
from dquant.constants import Constants
from dquant.markets.market import Market


class BitmexFutureWs(Market):
    def __init__(self, meta_code, loop):
        market_currency, base_currency, symbol = self.parse_meta(meta_code)
        super().__init__(market_currency, base_currency, meta_code, cfg.get_float_config(Constants.BITMEX_FEE))
        self.apikey = cfg.get_config(Constants.BITMEX_APIKEY)
        self.apisec = cfg.get_config(Constants.BITMEX_APISEC)
        self.base_url = Constants.BITMEX_FUTURE_WS_BASE
        self.bitmex_id = cfg.get_config(Constants.BITMEX_ID)
        self.symbol = symbol
        self.timeout = Constants.OK_HTTP_TIMEOUT
        self.position = {}
        self.update_flags = {"depth": False}
        self.websocket = None
        self.websocket_auth = None
        self.session = requests.session()
        self.client = MongoClient('localhost', 27017)
        self.db = self.client.account
        self.loop = loop
        self.depth = {}
        self.instruments = {}
        self.order = {}
        self.quote = {}
        self.ticker_trade = {}
        self.account = {}

        self.static_methods_register()

    async def sub_channel(self):
        '''

        The following subjects require authentication:
            "affiliate",   // Affiliate status, such as total referred users & payout %
            "execution",   // Individual executions; can be multiple per order
            "order",       // Live updates on your orders
            "margin",      // Updates on your current account balance and margin requirements
            "position",    // Updates on your positions
            "privateNotifications", // Individual notifications - currently not used
            "transact"     // Deposit/Withdrawal updates
            "wallet"       // Bitcoin address balance data, including total deposits & withdrawals
        '''
        # Send API Key with signed message.

        symbolSubs = ["instrument", "orderBook10", "orderBookL2", "quote", "trade", "execution", "order", "margin", "position"]
        subs = ["affiliate",  "privateNotifications", "transact", "wallet"]   # 这部分不要symbol的
        args = ['{}:{}'.format(sub, self.symbol) for sub in symbolSubs]
        args.extend(subs)
        messages = [{'op': 'subscribe', 'args': arg} for arg in args]
        for message in messages:
            await self.websocket.send(json.dumps(message))

    def bitmex_signature(self, verb, url, nonce, postdict=None):
        """Given an API Secret key and data, create a BitMEX-compatible signature."""
        data = ''
        if postdict:
            # separators remove spaces from json
            # BitMEX expects signatures from JSON built without spaces
            data = json.dumps(postdict, separators=(',', ':'))
        parsedURL = urlparse(url)
        path = parsedURL.path
        if parsedURL.query:
            path = path + '?' + parsedURL.query
        # print("Computing HMAC: %s" % verb + path + str(nonce) + data)
        message = (verb + path + str(nonce) + data).encode('utf-8')

        signature = hmac.new(self.apisec.encode('utf-8'), message, digestmod=hashlib.sha256).hexdigest()
        return signature


    def get_ticker(self, tillOk=True):
        '''Return a ticker object. Generated from quote and trade.'''

        while True:
            if not self.quote or not self.ticker_trade or not self.instruments:
                if tillOk:
                    time.sleep(10)
                    continue
            print('instr ..', self.instruments)
            lastQuote = self.quote[-1]
            lastTrade = self.ticker_trade[-1]
            ticker = {
                "last": lastTrade['price'],
                "buy": lastQuote['bidPrice'],
                "sell": lastQuote['askPrice'],
                "mid": (float(lastQuote['bidPrice'] or 0) + float(lastQuote['askPrice'] or 0)) / 2
            }

            # The instrument has a tickSize. Use it to round values.
            #instrument = self.instruments['instrument'][0]
            #instrument = self.data['instrument'][0]
            #return {k: round(float(v or 0), instrument['tickLog']) for k, v in ticker.items()}
            return ticker

    def bitmex_depth_format(self, res, flag):
        result_list = [{'price': float(ticker[0]), 'amount': float(ticker[1])} for ticker in res[flag]]
        if flag == "asks":  # 卖单从小到大
            result_list.sort(key=lambda x: x['price'])
        else:  # 买单从大到小
            result_list.sort(key=lambda x: x['price'], reverse=True)
        return result_list

    def getDepth(self):
        return self.depth

    def get_trade(self):
        '''
        :return: Live trades
        '''
        return self.ticker_trade

    def getOrder(self, order_id=None, clOrdID=None, tillOK=True):
        while True:
            try:
                res = self.trade(price=None, amount=None, type='get_order', orderID=order_id, clOrdID=clOrdID)
                if not res or 'error' in res:
                    if tillOK == True:
                        continue
                return res
            except Exception as ex:
                logging.exception("message")
                if tillOK:
                    continue
                return None

    def get_account(self):
        return self.account

    async def processing(self, flags):
        # 将所有Flag设置为False
        self.unset_flags(flags)
        while True:
            try:
                data = await self.websocket.recv()
                data = json.loads(data)
                # get channel and dispatch
                if 'table' in data:
                    channel = data["table"]
                    if (self.methods[channel] != None):
                        await self.methods[channel](data)
                    else:
                        pass
                # 反复经过self.methods[channel]处理ws返回的数据，直到所有Flag为真（即全部更新完毕）
                if (self.check_flags(flags)):
                    break
            except Exception as e:
                logging.exception("message")

    def static_methods_register(self):
        self.methods["orderBook10"] = self.update_depth  # 官方建议用orderBookL2， TODO
        self.methods['instrument'] = self.update_instruments
        self.methods['quote'] = self.update_quote
        self.methods['trade'] = self.update_trade

        self.methods['wallet'] = self.update_get_account
        self.methods["execution"] = self.update_execution
        self.methods['order'] = self.update_order
        self.methods["position"] = self.update_position

    # 更新depth，并且更新flag状态
    async def update_depth(self, depth_data):
        list_of_ask = self.bitmex_depth_format(depth_data["data"][0], "asks")
        list_of_bid = self.bitmex_depth_format(depth_data["data"][0], "bids")
        self.depth = {"asks": list_of_ask, 'bids': list_of_bid}
        self.update_flags["depth"] = True

    async def update_execution(self, data):

        #print('execution data; ', data)
        for order in data['data']:
            # 这里是order quantity
            if order['ordStatus'] == 'Filled':
                d = {'order_id': order['orderID'], 'amount_filled': order['orderQty'], 'trade_pair': order['symbol'],
                 'order_time': order['timestamp'], 'side': order['side'].lower(), 'account_id': order['account'], 'platform_id': 'bitmex'}

                d.update(self.position)
                d.update({"_id": datetime.datetime.utcnow(), 'timestamp': int(time.time() * 1000)})
                self.db.orders_bitmex.insert_one(d)

    async def update_position(self, data):
        symbol = data['data'][0]['symbol'] + '_position'
        currentQty = data['data'][0]['currentQty']
        self.position[symbol] = currentQty

    async def update_instruments(self, data):
        self.instruments = data

    async def update_order(self, data):
        self.order = data

    async def update_quote(self, data):
        self.quote = data['data']

    async def update_trade(self, data):
        self.ticker_trade = data['data']
        #print('ticker_trade: ', self.ticker_trade)

    async def update_get_account(self, data):
        self.account = data['data']

    # asyncio事件循环
    def update(self, flags):
        '''
        :param flags: {"depth": True, 'trade': False}
        :return:
        '''
        self.unset_flags(flags)

        while True:
            asyncio.sleep(1)
            if (self.check_flags(flags)):
                break
        return self

    def long(self, amount, price=-1, lever=None):
        '''
        # Websocket 不支持新增和取消委托。 此功能请使用 REST API。 在使用时保持 HTTP 连接，请求/响应的往返时间将与 Websocket 完全相同。
        :param amount: amount
        :param price: 价格，默认为Market
        :param lever: 0.01-100.与交易不在同一个API，因此如果自定义杠杆，需要等待设置杠杆对应的API返回才能下单。
        {'account': 122138, 'symbol': 'XBTUSD', 'currency': 'XBt', 'underlying': 'XBT', 'quoteCurrency': 'USD', 'commission': 0.00075, 'initMarginReq': 0.5, 'maintMarginReq': 0.005, 'riskLimit': 20000000000, 'leverage': 2, 'crossMargin': False, 'deleveragePercentile': 0.8, 'rebalancedPnl': 25, 'prevRealisedPnl': -25, 'prevUnrealisedPnl': 0, 'prevClosePrice': 9929.51, 'openingTimestamp': '2017-11-29T10:00:00.000Z', 'openingQty': 0, 'openingCost': -3, 'openingComm': 28, 'openOrderBuyQty': 0, 'openOrderBuyCost': 0, 'openOrderBuyPremium': 0, 'openOrderSellQty': 0, 'openOrderSellCost': 0, 'openOrderSellPremium': 0, 'execBuyQty': 0, 'execBuyCost': 0, 'execSellQty': 1, 'execSellCost': 9284, 'execQty': -1, 'execCost': 9284, 'execComm': -2, 'currentTimestamp': '2017-11-29T10:39:32.735Z', 'currentQty': -1, 'currentCost': 9281, 'currentComm': 26, 'realisedCost': -3, 'unrealisedCost': 9284, 'grossOpenCost': 0, 'grossOpenPremium': 0, 'grossExecCost': 9284, 'isOpen': True, 'markPrice': 10816.84, 'markValue': 9245, 'riskValue': 9245, 'homeNotional': -9.245e-05, 'foreignNotional': 1, 'posState': '', 'posCost': 9284, 'posCost2': 9284, 'posCross': 39, 'posInit': 4642, 'posComm': 11, 'posLoss': 0, 'posMargin': 4692, 'posMaint': 58, 'posAllowance': 0, 'taxableMargin': 0, 'initMargin': 0, 'maintMargin': 4653, 'sessionMargin': 0, 'targetExcessMargin': 0, 'varMargin': 0, 'realisedGrossPnl': 3, 'realisedTax': 0, 'realisedPnl': -23, 'unrealisedGrossPnl': -39, 'longBankrupt': 0, 'shortBankrupt': 0, 'taxBase': 0, 'indicativeTaxRate': 0, 'indicativeTax': 0, 'unrealisedTax': 0, 'unrealisedPnl': -39, 'unrealisedPnlPcnt': -0.0042, 'unrealisedRoePcnt': -0.0084, 'simpleQty': -0.0001, 'simpleCost': -1, 'simpleValue': -1, 'simplePnl': 0, 'simplePnlPcnt': 0, 'avgCostPrice': 10771, 'avgEntryPrice': 10771, 'breakEvenPrice': 10773.5, 'marginCallPrice': 21505, 'liquidationPrice': 21505, 'bankruptPrice': 21724.5, 'timestamp': '2017-11-29T10:39:32.735Z', 'lastPrice': 10816.84, 'lastValue': 9245}
        :return:{'orderID': '08601c74-334a-8d6c-503c-541761cdb00e', 'clOrdID': '', 'clOrdLinkID': '', 'account': 122138, 'symbol': 'XBTUSD', 'side': 'Buy', 'simpleOrderQty': None, 'orderQty': 1, 'price': 10759, 'displayQty': None, 'stopPx': None, 'pegOffsetValue': None, 'pegPriceType': '', 'currency': 'USD', 'settlCurrency': 'XBt', 'ordType': 'Market', 'timeInForce': 'ImmediateOrCancel', 'execInst': '', 'contingencyType': '', 'exDestination': 'XBME', 'ordStatus': 'Filled', 'triggered': '', 'workingIndicator': False, 'ordRejReason': '', 'simpleLeavesQty': 0, 'leavesQty': 0, 'simpleCumQty': 9.284e-05, 'cumQty': 1, 'avgPx': 10758.5, 'multiLegReportingType': 'SingleSecurity', 'text': 'Submitted via API.', 'transactTime': '2017-11-29T10:39:33.377Z', 'timestamp': '2017-11-29T10:39:33.377Z'}
        '''
        if lever:
            res_l = self.trade(price=None, amount=None, type='set_lever', lever=lever)
            print(res_l)
        price = float(price) if price > 0 else None
        res = self.trade(price=price, amount=abs(float(amount)), type='long')
        return res

    def short(self, amount, price=-1, lever=None):
        if lever:
            res_l = self.trade(price=None, amount=None, type='set_lever', lever=lever)
            print(res_l)
        price = float(price) if price > 0 else None
        res = self.trade(price=price, amount=-abs(float(amount)), type='short')
        return res

    def closeLong(self, price=-1, amount=None):
        '''
        :param amount: 这是个无效的参数，bitmex不能选择数量
        :param price: close_long与close_short是一样的功能，如果留空则是以市价平仓当前货币所有头寸，否则为限价
        :return:
        '''
        price = float(price) if price > 0 else None
        res = self.trade(price=price, amount=None, type='close_long')
        return res

    def closeShort(self, price=-1, amount=None):
        price = float(price) if price > 0 else None
        res = self.trade(price=price, amount=None, type='close_short')
        return res

    def deleteOrder(self, order_id=None, clOrdID=None ,tillOK=True):
        '''
        :param orderID:Either an orderID or a clOrdID must be provided.
        :param clOrdID:
        :return:[{'orderID': 'd4e91f38-514e-d4cb-89df-9cf95266f693', 'clOrdID': '', 'clOrdLinkID': '', 'account': 122138, 'symbol': 'XBTUSD', 'side': 'Sell', 'simpleOrderQty': None, 'orderQty': 1, 'price': 10771.5, 'displayQty': None, 'stopPx': None, 'pegOffsetValue': None, 'pegPriceType': '', 'currency': 'USD', 'settlCurrency': 'XBt', 'ordType': 'Limit', 'timeInForce': 'GoodTillCancel', 'execInst': '', 'contingencyType': '', 'exDestination': 'XBME', 'ordStatus': 'Filled', 'triggered': '', 'workingIndicator': False, 'ordRejReason': '', 'simpleLeavesQty': 0, 'leavesQty': 0, 'simpleCumQty': 9.284e-05, 'cumQty': 1, 'avgPx': 10771, 'multiLegReportingType': 'SingleSecurity', 'text': 'Submitted via API.', 'transactTime': '2017-11-29T10:02:03.591Z', 'timestamp': '2017-11-29T10:03:01.806Z', 'error': 'Unable to cancel order due to existing state: Filled'}]
        '''
        while True:
            try:
                if order_id or clOrdID:
                    res = self.trade(price=None, amount=None, type='delete_order', orderID=order_id, clOrdID=clOrdID)
                else:
                    logging.exception('Either an orderID or a clOrdID must be provided.')
                    return None
                if tillOK:
                    order = self.getOrder(order_id=order_id, clOrdID=clOrdID)
                    ordStatus = order[0] if 'ordStatus' in order[0] else ''
                    # 订单如果仍然active，则需要重新取消
                    if ordStatus in ['New', 'Partially Filled']:
                        continue
                        # 订单已经Filled或者Canceled
                return res
            except Exception as ex:
                logging.exception("message")
                if tillOK:
                    continue
                return None

    def trade(self, price, amount, type, **args):
        # 删除订单，method=DELETE
        if type == 'delete_order':
            url = Constants.BITMEX_FUTURE_ORDER
            orderID = args.get('orderID', None)
            clOrdID = args.get('clOrdID', None)
            data = {'orderID': orderID} if orderID else {'clOrdID': clOrdID}
            res = self.request(url, data=data, type='delete')

        # 获取订单
        elif type == 'get_order':
            url = Constants.BITMEX_FUTURE_ORDER
            orderID = args.get('orderID', None)
            clOrdID = args.get('clOrdID', None)
            filter = json.dumps({'orderID': orderID} if orderID else {'clOrdID': clOrdID})
            params = {'symbol': self.symbol, 'filter': filter}
            res = self.request(url, params=params, type='get')

        # 设置杠杆, method=POST
        elif type == 'set_lever':
            url = Constants.BITMEX_FUTURE_LEVER
            lever = args.get('lever')
            data = {'symbol': self.symbol, 'leverage': lever}
            res = self.request(url, data=data, type='post')

        # 新订单， method=POST
        else:
            if type == 'long' or type == 'short':
                url = Constants.BITMEX_FUTURE_ORDER
            else:
                url = Constants.BITMEX_FUTURE_CLOSE_POSITION
            ordType = 'Limit' if price else 'Market'
            data = {'symbol': self.symbol, 'orderQty': amount, 'ordType': ordType}
            if price:
                data['price'] = price
            res = self.request(url, data=data, type='post')

        return res

    def buildMySign(self, full_url, nonce, data, method="GET"):
        data = json.dumps(data, separators=(',', ':')) if data else ''
        parsedURL = urlparse(full_url)
        path = parsedURL.path
        if parsedURL.query:
            path = path + '?' + parsedURL.query
        message = method + path + str(nonce) + data
        signature = hmac.new(bytes(self.apisec, 'utf8'), bytes(message, 'utf8'), digestmod=hashlib.sha256).hexdigest()
        return signature

    def request(self, url, type, params=None, data=None):
        nonce = int(round(time.time() * 1000))
        full_url = url + '?' + urlencode(params) if params else url
        headers = {
            'api-nonce': str(nonce),
            'api-key': self.apikey,
            'api-signature': self.buildMySign(full_url=full_url, nonce=nonce, data=data, method=type.upper())
        }
        if type == "post":
            headers['Content-Type'] = 'application/json'
            data = json.dumps(data, separators=(',', ':')) if data else ''
            res = self.session.post(url=url, data=data, timeout=self.timeout, headers=headers)
        elif type == "get":
            res = self.session.get(url=url, params=params, timeout=self.timeout, headers=headers)
        elif type == 'delete':
            headers['Content-Type'] = 'application/json'
            data = json.dumps(data, separators=(',', ':')) if data else ''
            res = self.session.delete(url=url, data=data, timeout=self.timeout, headers=headers)

        if res.status_code == 200:
            #return json.loads(res.content.decode('utf-8'))
            return res.json()
        else:
            print(res.content)
            logging.exception("request error")
        return res.json()

    async def ws_handler(self):
        '''
        handle task in backthread
        :return:
        '''
        while True:
            try:
                data = await asyncio.wait_for(self.websocket.recv(), timeout=20)
            except asyncio.TimeoutError:
                # No data in 20 seconds, check the connection.
                try:
                    pong_waiter = await self.websocket.ping()
                    await asyncio.wait_for(pong_waiter, timeout=10)
                except asyncio.TimeoutError:
                    # No response to ping in 10 seconds, disconnect.
                    logging.error('ws_handler: receive time out')
                    break
            else:
                data = json.loads(data)
                # get channel and dispatch
                if 'table' in data:
                    #if data['table'] not in ['orderBookL2', 'trade', 'instrument', 'quote']:
                    #    print('data: {}'.format(data['table']))
                    channel = data["table"]
                    if channel in self.methods:
                        await self.methods[channel](data)
                    else:
                        pass

    def parse_meta(self, meta_code):
        meta_table = {"btc_usd": ("btc", "usd", "XBTUSD"), }
        return meta_table[meta_code]

    def run(self):
        asyncio.set_event_loop(self.loop)
        while True:
            try:
                self.loop.run_until_complete(self.keep_connect())
                tasks = [self.ws_handler()]
                self.loop.run_until_complete(asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED))
                time.sleep(2)
            except Exception as ex:
                logging.error(ex)

    async def keep_connect(self):
        reconnect_count = 1
        while True:
            try:
                if self.websocket == None:
                    try:
                        nonce = int(round(time.time() * 1000))
                        ENDPOINT = "/realtime"
                        # See signature generation reference at https://www.bitmex.com/app/apiKeys
                        signature = self.bitmex_signature("GET", ENDPOINT, nonce)
                        #self.websocket = await websockets.connect(self.base_url, timeout=20)

                        # 用auth socket
                        self.websocket = await websockets.connect(self.base_url + "?api-nonce=%s&api-signature=%s&api-key=%s" % (nonce, signature, self.apikey))

                        request = {"op": "authKey", "args": [self.apikey, nonce, signature]}
                        self.websocket.send(json.dumps(request))
                    except Exception as ex:
                        print('%s websocket keep_connect timeout' % self.name)
                else:
                    if not self.websocket.open:
                        await self.websocket.close()
                        print('%s websocket closed, reconnect' % self.name)
                        try:
                            self.websocket = await websockets.connect(self.base_url, timeout=20)
                        except Exception as ex:
                            print('%s websocket keep_connect timeout' % self.name)
                    else:
                        print('%s websocket connected' % self.name)
                        break
            except Exception as ex:
                print("keep_connect: %s" % ex)
                # continue
            finally:
                reconnect_count += 1
                await asyncio.sleep(0.5)
        await self.sub_channel()


if __name__ == '__main__':
    os.environ[Constants.DQUANT_ENV] = "dev"
    loop = asyncio.get_event_loop()
    bmex = BitmexFutureWs('btc_usd', loop)
    bmex.start()
    time.sleep(20)
    while True:
        #print(bmex.get_ticker())
        print(bmex.getDepth())
        #print(bmex.get_trade())
        #print(bmex.get_account())
        time.sleep(10)