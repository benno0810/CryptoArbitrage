import threading
import queue
import sys
import collections

import time

import websockets
from copy import copy

sys.path.append('../../')
import asyncio
import logging
from dquant.config import cfg
from dquant.constants import Constants
import hashlib
import json
import requests
import requests.adapters
from dquant.markets.market import Market
from dquant.markets._binance_spot_rest import Binance
from dquant.util import Util
import os

requests.adapters.DEFAULT_RETRIES = 5
delay_time = 0.1

logger = logging.getLogger(__name__)

class BinanceSpotDepthWs(Market):
    def __init__(self, meta_code, loop):
        market_currency, base_currency, symbol = self.parse_meta(meta_code)
        super().__init__(market_currency, base_currency, meta_code, cfg.get_float_config(Constants.BINANCE_FEE))
        self.apikey = cfg.get_config(Constants.BINANCE_APIKEY)
        self.apisec = cfg.get_config(Constants.BINANCE_APISEC)
        self.fee_rate_taker = cfg.get_float_config(Constants.BINANCE_FEE_TAKER)
        self.name = 'Binance'
        self.symbol = symbol
        # self.minimum_amount = cfg.get_config(Constants.BINANCE_MINIMUM_AMOUNT)
        self.strategy_id = cfg.get_config(Constants.BINANCE_STRATEGY_ID)
        self.base_url_api = ' https://api.binance.com'
        self.timeout = Constants.OK_HTTP_TIMEOUT
        self.loop = loop
        self.websocket = None
        self.streamName = '{}@depth20'.format(self.symbol.replace('_', ''))
        self.base_url = 'wss://stream.binance.com:9443/ws/{}'.format(self.streamName)
        self.depth = {}


    async def sub_channel(self):
        pass

    def run(self):
        asyncio.set_event_loop(self.loop)
        while True:
            try:
                self.loop.run_until_complete(self.keep_connect())
                tasks = [self.ws_handler()]
                self.loop.run_until_complete(asyncio.wait(tasks))
            except Exception as ex:
                self.error(ex)

    def parse_meta(self, meta_code):
        meta_table = {"eth_usdt": ("eth", "usdt", "eth_usdt"),
                      "btc_usdt": ("btc", "usdt", "btc_usdt"),
                      "eth_btc": ("eth", "btc", "eth_btc"),
                      'eos_eth': ('eos', 'eth', 'eos_eth'),
                      'eos_btc': ('eos', 'btc', 'eos_btc'),
                      'bcc_eth': ('bcc', 'eth', 'bcc_eth'),
                      'bch_eth': ('bcc', 'eth', 'bcc_eth'),
                      'bcc_btc': ('bcc', 'btc', 'bcc_btc'),
                      'bch_btc': ('bcc', 'btc', 'bcc_btc'),
                      'bnb_usdt': ('BNB', 'USDT', 'BNBUSDT'),
                      }
        return meta_table[meta_code]

    def get_depth(self):
        if self.depth:
            self.depth['bids'].sort(key=lambda item: item['price'], reverse=True)
            self.depth['asks'].sort(key=lambda item: item['price'], reverse=False)
        return self.depth

    def depth_format(self, list):
        return [{'price': float(item[0]), 'amount': float(item[1])} for item in list]

    async def update_depth(self, data):
        self.depth = {'bids': self.depth_format(data['bids']), 'asks': self.depth_format(data['asks'])}

    async def ws_handler(self):
        '''
        handle task in backthread
        handle task in backthread
        :return:
        '''
        while True:
            try:
                data = await asyncio.wait_for(self.websocket.recv(), timeout=10)
            except Exception as ex:
                try:
                    self.error('Binance SpotDepth ws_handler: %s' % ex)
                    await self.keep_connect()
                    self.depth = {}
                except Exception:
                    self.depth = {}
                    break
            else:
                data = json.loads(data)
                # print(data)
                if data:
                    await self.update_depth(data)


class BinanceSpotWs(Market):
    def __init__(self, meta_code, loop):
        market_currency, base_currency, symbol = self.parse_meta(meta_code)
        super().__init__(market_currency, base_currency, meta_code, cfg.get_float_config(Constants.BINANCE_FEE))
        self.apikey = cfg.get_config(Constants.BINANCE_APIKEY)
        self.apisec = cfg.get_config(Constants.BINANCE_APISEC)
        self.binance_id = cfg.get_config(Constants.BINANCE_ID)
        self.strategy_id = cfg.get_config(Constants.BINANCE_STRATEGY_ID)
        self.fee_rate_taker = cfg.get_float_config(Constants.BINANCE_FEE_TAKER)
        self.base_url_api = ' https://api.binance.com'
        self.name = 'Binance'
        self.symbol = symbol
        # ['min_amount', 'price', 'amount']
        [self.minimum_amount, self.price_precision, self.amount_precision] = cfg.get_precisions(self.name, market_currency+base_currency)
        if not (self.price_precision and self.amount_precision):
            self.minimum_amount = cfg.get_float_config(Constants.BINANCE_MINIMUM_AMOUNT)
            self.amount_precision = cfg.get_int_config(Constants.BINANCE_AMOUNT_PRECISION)
            self.price_precision = cfg.get_int_config(Constants.BINANCE_PRICE_PRECISION)
        self.timeout = Constants.OK_HTTP_TIMEOUT
        self.loop = loop
        self.websocket = None
        self.listenkey = ''
        self.create_listenkey()
        self.base_url = 'wss://stream.binance.com:9443/ws/{}'.format(self.listenkey)
        self.register_callbacks()
        self.account = {}
        self.orders = {}
        self.pid = os.getpid()
        self.hist = {'buy': collections.OrderedDict(), 'sell': collections.OrderedDict()}
        self.hist_lenth = 10
        self.order_result_required = False
        self.q_order_result = queue.Queue()

        self.binance_rest = Binance(meta_code)

        self.DepthWs = BinanceSpotDepthWs(meta_code, asyncio.new_event_loop())
        self.DepthWs.setDaemon(True)
        self.DepthWs.start()
        update_listen_key_event = threading.Event()
        self.updateListenKeyThread(update_listen_key_event, 1000)
        self.api_lock = threading.Lock()

    def getDepth(self):
        s_time = time.time()
        self.binance_rest.strategy_id = self.strategy_id
        depth = self.DepthWs.get_depth()
        if depth:
            self.compute_latency(s_time, 'depth')
            return depth
        logger.info("Binance getDepth: using REST api")
        return self.binance_rest.getDepth()


    async def keep_connect(self):
        while True:
            try:
                self.create_listenkey()
                self.base_url = 'wss://stream.binance.com:9443/ws/{}'.format(self.listenkey)
                if self.websocket == None:
                    self.websocket = await websockets.connect(self.base_url)
                else:
                    if not self.websocket.open:
                        self.websocket.close()
                        self.websocket = await websockets.connect(self.base_url)
                    else:
                        logger.info('Binance Spot websocket connected')
                        break
            except Exception as ex:
                self.error(ex)
                # continue
            finally:
                await asyncio.sleep(1)
        await self.sub_channel()


    def run(self):
        asyncio.set_event_loop(self.loop)
        while True:
            try:
                self.loop.run_until_complete(self.keep_connect())
                # self.loop.run_until_complete(self.ws_init())
                tasks = [self.ws_handler()]
                self.loop.run_until_complete(asyncio.wait(tasks))
                time.sleep(5)
            except Exception as ex:
                self.error(ex)

    def get_depth(self):
        return self.DepthWs.get_depth()

    def create_listenkey(self):
        while True:
            try:
                headers = {
                    "Content-type": "application/x-www-form-urlencoded",
                    "X-MBX-APIKEY": self.apikey
                }
                res = requests.post(self.base_url_api + '/api/v1/userDataStream', headers=headers)
                # print(res.json())
                if res.status_code == 200:
                    self.listenkey = res.json()['listenKey']
                    # print(self.listenkey)
                    break
                else:
                    logger.error("Binance create_listenkey(status != 200): %s, Retry." % res.json())
                time.sleep(0.5)
            except Exception as ex:
                logger.error("Binance create_listenkey: %s" % ex)

    def updateListenKeyThread(self, update_listen_key_event, seconds):
        self.update_listenkey()
        if not update_listen_key_event.is_set():
            timer = threading.Timer(seconds, self.updateListenKeyThread, [update_listen_key_event,seconds])
            timer.setDaemon(True)
            timer.start()

    def update_listenkey(self):
        headers = {
            "Content-type": "application/x-www-form-urlencoded",
            "X-MBX-APIKEY": self.apikey
        }
        data = {'listenKey': self.listenkey}
        res = requests.put(self.base_url_api + '/api/v1/userDataStream', data=data, headers=headers)
        # print('update listen',res)

        # put操作没有返回值
        if res.status_code == 200:
            pass
            # print('succeed')

    def buildMySign(self, params, secretKey):
        sign = ''
        for key in sorted(params.keys()):
            sign += key + '=' + str(params[key]) + '&'
        data = sign + 'secret_key=' + secretKey
        return hashlib.md5(data.encode("utf8")).hexdigest().upper()

    def register_callbacks(self):
        self.methods['outboundAccountInfo'] = self.update_account
        self.methods['executionReport'] = self.update_orders

    async def update_account(self, account_data):
        '''
        :param account_data:
        {
          "e": "outboundAccountInfo",   // Event type
          "E": 1499405658849,           // Event time
          "m": 0,                       // Maker commission rate (bips)
          "t": 0,                       // Taker commission rate (bips)
          "b": 0,                       // Buyer commission rate (bips)
          "s": 0,                       // Seller commission rate (bips)
          "T": true,                    // Can trade?
          "W": true,                    // Can withdraw?
          "D": true,                    // Can deposit?
          "u": 1499405658848,           // Time of last account update
          "B": [                        // Balances array
            {
              "a": "LTC",               // Asset
              "f": "17366.18538083",    // Free amount
              "l": "0.00000000"         // Locked amount
            },
            {
              "a": "BTC",
              "f": "10537.85314051",
              "l": "2.19464093"
            },
            {
              "a": "ETH",
              "f": "17902.35190619",
              "l": "0.00000000"
            },
            {
              "a": "BNC",
              "f": "1114503.29769312",
              "l": "0.00000000"
            },
            {
              "a": "NEO",
              "f": "0.00000000",
              "l": "0.00000000"
            }
          ]
        }
        :return:
        '''
        ans = {}
        for b in account_data['B']:
            if float(b['f']) > 0:
                ans[b['a']] = float(b['f'])
        with self.api_lock:
            self.account = ans

    async def update_orders(self, orders_data):
        # print('orders_data!!!orders_data',orders_data)
        '''
        :param orders_data:
        {
          "e": "executionReport",        // Event type
          "E": 1499405658658,            // Event time
          "s": "ETHBTC",                 // Symbol
          "c": "mUvoqJxFIILMdfAW5iGSOW", // Client order ID
          "S": "BUY",                    // Side
          "o": "LIMIT",                  // Order type
          "f": "GTC",                    // Time in force
          "q": "1.00000000",             // Order quantity
          "p": "0.10264410",             // Order price
          "P": "0.00000000",             // Stop price
          "F": "0.00000000",             // Iceberg quantity
          "g": -1,                       // Ignore
          "C": "null",                   // Original client order ID; This is the ID of the order being canceled
          "x": "NEW",                    // Current execution type
          "X": "NEW",                    // Current order status
          "r": "NONE",                   // Order reject reason; will be an error code.
          "i": 4293153,                  // Order ID
          "l": "0.00000000",             // Last executed quantity
          "z": "0.00000000",             // Cumulative filled quantity
          "L": "0.00000000",             // Last executed price
          "n": "0",                      // Commission amount
          "N": null,                     // Commission asset
          "T": 1499405658657,            // Transaction time
          "t": -1,                       // Trade ID
          "I": 8641984,                  // Ignore
          "w": true,                     // Is the order working? Stops will have
          "m": false,                    // Is this trade the maker side?
          "M": false                     // Ignore
        }
        :return:
        '''
        if orders_data:
            order_id = int(orders_data['i'])
            side = orders_data['S'].lower()
            execution_type = orders_data.get("x")
            amount_filled = float(orders_data.get('z'))
            amount_filled_this_time = float(orders_data.get('l'))
            amount_orig = float(orders_data.get('q'))
            # 若是市价成交，取上一次成交价格
            price = float(orders_data.get('p')) or float(orders_data.get('L'))
            trade_pair = orders_data.get('s')
            time_stamp = orders_data.get('T')
            client_order_id = orders_data.get('c')
            client_order_id_orig = orders_data.get('C')
            status = orders_data.get('X')
            pid = Util.bnc_pid_from_cid(client_order_id) or Util.bnc_pid_from_cid(client_order_id_orig)
            if pid and int(pid) == int(self.pid):
                order_data = Util.build_order_result(status=True, order_id=order_id, side=side,
                                            trade_pair=trade_pair, price=price, amount_filled=amount_filled,
                                            amount_filled_this_time=amount_filled_this_time, amount_orig=amount_orig, platform_id='binance')
                # print(execution_type, order_data)

                if execution_type in ['CANCELED', 'TRADE']:
                    if amount_filled_this_time:
                        if self.order_result_required:
                            logger.debug("Binance q_order_result: %s" % order_data)
                            self.q_order_result.put(order_data)
                    if (status == 'FILLED') or (status == 'CANCELED' and amount_filled):
                        fee_rate = self.fee_rate if float(orders_data.get('p')) else self.fee_rate_taker

                        if side.find('buy') != -1:
                            fee = '{}_{}'.format('%.8f' % (float(amount_filled) * float(fee_rate)), self.market_currency)
                        else:
                            fee = '{}_{}'.format('%.8f' % (float(amount_filled) * float(price) * fee_rate), self.base_currency)

                        data_store = Util.build_order_store(order_id=order_id, side=side, trade_pair=trade_pair,
                            price=price, amount_filled=amount_filled, time_stamp=time_stamp,
                            client_order_id=client_order_id, platform_name='binance', platform_account_id=self.binance_id,
                            strategy_id=self.strategy_id, fee=fee)

                        self.q_orders.put(data_store)
                        if self.isTaker:
                            self.q_taker_order_result.put(data_store)

                if execution_type in ['CANCELED', 'REPLACED', 'REJECTED', 'EXPIRED']:
                    try:
                        del self.orders[order_id]
                    except:
                        pass

                elif execution_type == 'TRADE':
                    if amount_orig == amount_filled:
                        try:
                            self.hist[side][order_id] = order_data
                            if len(self.hist[side]) > self.hist_lenth:
                                self.hist[side].popitem(last=False)
                            del self.orders[order_id]
                        except:
                            pass
                    else:
                        self.orders[order_id] = order_data

                else:
                    self.orders[order_id] = order_data

                if status.upper() == 'FILLED':
                    try:
                        del self.orders[order_id]
                    except:
                        pass

    def getHist(self, order_id=None, side=None):
        if order_id and side:
            if order_id in self.hist[side]:
                return self.hist[side][order_id]
            else:
                return Util.build_order_result(status=False)
        return self.hist

    # def getDepth(self):
    #     return self.binance_rest.getDepth()

    def getAccount(self, coin=[]):
        if not self.account:
            logger.debug("Binance getAccount: using rest API")
            initial_account_data = self.binance_rest.getAccount(coin=coin)
            with self.api_lock:
                self.account = initial_account_data
            return initial_account_data
        ret = {}
        for c in coin:
            ret[c.upper()] = 0.0
        with self.api_lock:
            for c in coin:
                if c.upper() in self.account:
                    ret[c.upper()] = self.account[c.upper()]
        return ret

    # def getAccount(self, coin=[]):
    #     return self.binance_rest.getAccount(coin=coin)

    def buy(self, amount, price=-1):
        # 因为是调用REST接口，所以不需要把这里的数据入库
        amount = round(amount, self.amount_precision)
        if price > 0:
            price = round(price, self.price_precision)
        # print(amount, price)
        result = self.binance_rest.buy(amount=amount, price=price)
        logger.debug('Binance Buy: %s' % result)
        if result['status']:
            self.orders[result['order_id']] = result
            return result
        else:
            return None

    def sell(self,amount,price=-1):
        amount = round(amount, self.amount_precision)
        if price > 0:
            price = round(price, self.price_precision)
        result = self.binance_rest.sell(amount=amount, price=price)
        logger.debug('Binance Sell: %s' % result)
        if result['status']:
            self.orders[result['order_id']] = result
            return result
        else:
            return None

    def deleteOrder(self, order_id):
        # 因为这里是调用REST类，所以不需要重复的将cancelled order入库
        result = self.binance_rest.deleteOrder(order_id=order_id)
        logger.debug('Binance deleteOrder: %s' % result)
        return result

    # def getOrder(self, order_id):
    #     return self.binance_rest.getOrder(order_id=order_id)

    def getOrder(self, order_id):
        if order_id:
            order_id = int(order_id)
            # print('getOrder', self.orders)
            if order_id in self.orders:
                return self.orders[order_id]
        return Util.build_order_result(status=False, order_id=order_id)

    def getAllOrders(self):
        if self.orders:
            return [order for order in self.orders]
        else:
            return []

    def parse_meta(self, meta_code):
        meta_table = {"eth_usdt": ("ETH", "USDT", "ETHUSDT"),
                      "btc_usdt": ("BTC", "USDT", "BTCUSDT"),
                      "eth_btc": ("ETH", "BTC", "ETHBTC"),
                      'eos_eth': ('EOS', 'ETH', 'EOSETH'),
                      'eos_btc': ('EOS', 'BTC', 'EOSBTC'),
                      'bcc_eth': ('BCC', 'ETH', 'BCCETH'),
                      'bch_eth': ('BCC', 'ETH', 'BCCETH'),
                      'bcc_btc': ('BCC', 'BTC', 'BCCBTC'),
                      'bch_btc': ('BCC', 'BTC', 'BCCBTC'),
                      'bnb_usdt': ('BNB', 'USDT', 'BNBUSDT'),
                      }
        return meta_table[meta_code]

    async def sub_channel(self):
        pass

    async def ws_init(self):
        await self.sub_channel()

    async def ws_handler(self):
        '''
        handle task in backthread
        :return:
        '''
        while True:
            try:
                data = await self.websocket.recv()
            except Exception as ex:
                try:
                    self.error('Binance ws_handler: %s' % ex)
                    await self.keep_connect()
                    continue
                except Exception as ex:
                    self.error('Binance ws_handler: %s' % ex)
                    break
            else:
                data = json.loads(data)
                # print(data)
                event = data.get('e', '')
                if not event:
                    continue
                if self.methods[event] != None:
                    await self.methods[event](data)
                else:
                    pass


if __name__ == '__main__':
    os.environ[Constants.DQUANT_ENV] = "dev"

    loop = asyncio.get_event_loop()
    bi_ws = BinanceSpotWs('bnb_usdt', loop)
    bi_ws.setDaemon(True)
    bi_ws.start()

    time.sleep(10)

    print(bi_ws.buy(0.1))

    time.sleep(10)

    print(bi_ws.sell(0.1))

    time.sleep(10)

    while True:
        #result = bi_ws.getDepth()
        #print(result)

        time.sleep(2)