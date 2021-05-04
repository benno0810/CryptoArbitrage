from __future__ import absolute_import
import sys
sys.path.append('../../')
from datetime import datetime
import requests
import json
import base64
import hmac
import hashlib
import time
import os
from dquant.constants import Constants
from dquant.markets.market import Market
from dquant.config import cfg
from dquant.common.mongo_conn import MongoConnTrade
from dquant.common.depth_log import init_roll_log


logger = init_roll_log('bitfinex_spot_rest.log')
PROTOCOL = "https"
HOST = "api.bitfinex.com"
VERSION = "v1"

PATH_SYMBOLS = "symbols"
PATH_TICKER = "ticker/%s"
PATH_TODAY = "today/%s"
PATH_STATS = "stats/%s"
PATH_LENDBOOK = "lendbook/%s"
PATH_ORDERBOOK = "book/%s"

# HTTP request timeout in seconds
TIMEOUT = 5.0


class TradingV1(Market):
    """
    Authenticated client for trading through Bitfinex API
    """

    def __init__(self, meta_code):
        base_currency, market_currency, symbol = self.parse_meta(meta_code)
        super().__init__(market_currency, base_currency, meta_code, cfg.get_float_config(Constants.BITFINEX_FEE))
        self.symbol = symbol
        self.URL = "{0:s}://{1:s}/{2:s}".format(PROTOCOL, HOST, VERSION)
        self.KEY = cfg.get_config(Constants.BITFINEX_APIKEY)
        self.SECRET = cfg.get_config(Constants.BITFINEX_APISEC)
        self.base_url = 'https://api.bitfinex.com'
        self.db = MongoConnTrade().client.get_database('trade_bfx')
        self.collection = self.db.get_collection(self.symbol.lower())
        self.name = 'Bitfinex'

    def parse_meta(self, meta_code):
        meta_table = {'eth_usd': ("ETH", "USD", "ETHUSD"),
                      'btc_usd': ("BTC", "USD", "BTCUSD"),
                      'eth_btc': ("ETH", "BTC", "ETHBTC"),
                      'bnb_btc': ('BNB', 'BTC', 'BNBBTC'),
                      'bnb_usd': ('BNB', 'USD', 'BNBUSD'),
                      'ltc_eth': ('LTC', 'ETH', 'LTCETH'),
                      'ltc_bnb': ('LTC', 'BNB', 'LTCBNB'),
                      'bcc_usd': ('BCC', 'USD', 'BCCUSD'),
                      'bcc_bnb': ('BCC', 'BNB', 'BCCBNB'),
                      'bcc_btc': ('BCC', 'BTC', 'BCCBTC'),
                      'ven_bnb': ('VEN', 'BNB', 'VENBNB'),
                      'bnb_eth': ('BNB', 'ETH', 'BNBETH'),
                      'ven_eth': ('VEN', 'ETH', 'VENETH'),
                      'bcc_eth': ('BCC', 'ETH', 'BCCETH'),
                      'ltc_btc': ('LTC', 'BTC', 'LTCBTC'),
                      'ltc_usd': ('LTC', 'USD', 'LTCUSD'),
                      "eth_usdt": ("ETH", "USD", "ETHUSD"),
                      "btc_usdt": ("BTC", "USD", "BTCUSD"),
                      'eos_eth': ('EOS', 'ETH', 'EOSETH'),
                      'bch_eth': ('BCH', 'ETH', 'BCHETH'),
                      'eos_btc': ('EOS', 'BTC', 'EOSBTC'),
                      'bch_btc': ('BCH', 'BTC', 'BCHBTC'),
                      }
        return meta_table[meta_code]

    @property
    def _nonce(self):
        """
        Returns a nonce
        Used in authentication
        """
        return str(time.time() * 1000000)

    def _sign_payload(self, payload):
        j = json.dumps(payload)
        data = base64.standard_b64encode(j.encode('utf8'))

        h = hmac.new(self.SECRET.encode('utf8'), data, hashlib.sha384)
        signature = h.hexdigest()
        return {
            "X-BFX-APIKEY": self.KEY,
            "X-BFX-SIGNATURE": signature,
            "X-BFX-PAYLOAD": data
        }

    def place_order(self, amount, price, side, ord_type, symbol='btcusd', exchange='bitfinex'):
        """
        Submit a new order.
        :param amount:
        :param price:
        :param side:
        :param ord_type:
        :param symbol:
        :param exchange:
        :return:
        """
        payload = {

            "request": "/v1/order/new",
            "nonce": self._nonce,
            "symbol": symbol,
            "amount": amount,
            "price": price,
            "exchange": exchange,
            "side": side,
            "type": ord_type

        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/order/new", headers=signed_payload, verify=True)
        json_resp = r.json()
        print('rsp:', json_resp)
        try:
            json_resp['order_id']
        except:
            return json_resp['message']

        return json_resp

    def delete_order(self, order_id):
        """
        Cancel an order.
        :param order_id:
        :return:
        """
        payload = {
            "request": "/v1/order/cancel",
            "nonce": self._nonce,
            "order_id": order_id
        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/order/cancel", headers=signed_payload, verify=True)
        json_resp = r.json()

        try:
            json_resp['avg_execution_price']
        except:
            return json_resp['message']

        return json_resp

    def cancel_active_orders(self):
        """
        Cancel all active orders at once.
        :return:
        """
        # payload = {
        #     "request": "/v1/order/cancel/all",
        #     "nonce": self._nonce,
        # }
        #
        # signed_payload = self._sign_payload(payload)
        # r = requests.post(self.URL + "/order/cancel/all", headers=signed_payload, verify=True)
        # json_resp = r.json()
        # print('can res: ', r.json())
        # return json_resp
        ret = []
        res = self.get_active_orders()
        for o in res:
            if o["symbol"].upper() == self.symbol:
                res = self.delete_order(o["id"])
                print(res)
                ret.append(res)
        return ret

    def withdraw(self, asset, address, amount):
        '''
        :param asset:
        :param address:
        :param amount:
        :return:
        '''

        payload = {
            "request": "/v1/withdraw",
            "withdraw_type": asset,
            "walletselected": "exchange", # 这个写死
            "amount": amount,
            "address": address,
            "nonce": self._nonce,
        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.base_url+ "/v1/withdraw", headers=signed_payload, verify=True)
        #rsp = r.json()
        print('withdraw res: {}, {}'.format(r, r.json()))

    def status_order(self, order_id):
        """
        Get the status of an order. Is it active? Was it cancelled? To what extent has it been executed? etc.
        :param order_id:
        :return:
        """
        payload = {
            "request": "/v1/order/status",
            "nonce": self._nonce,
            "order_id": order_id
        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/order/status", headers=signed_payload, verify=True)
        json_resp = r.json()

        try:
            json_resp['avg_execution_price']
        except:
            return json_resp['message']

        return json_resp

    def get_active_orders(self):
        """
        Fetch active orders
        """

        payload = {
            "request": "/v1/orders",
            "nonce": self._nonce
        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/orders", headers=signed_payload, verify=True)
        # print('get_active_orders: ', r.json())
        return r.json()

    def active_positions(self):
        """
        Fetch active Positions
        """

        payload = {
            "request": "/v1/positions",
            "nonce": self._nonce
        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/positions", headers=signed_payload, verify=True)
        json_resp = r.json()
        return json_resp

    def claim_position(self, position_id):
        """
        Claim a position.
        :param position_id:
        :return:
        """
        payload = {
            "request": "/v1/position/claim",
            "nonce": self._nonce,
            "position_id": position_id
        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/position/claim", headers=signed_payload, verify=True)
        json_resp = r.json()

        return json_resp

    def past_trades(self, timestamp=int(time.time()), symbol='btcusd'):
        """
        Fetch past trades
        :param timestamp:
        :param symbol:
        :return:
        """

        payload = {
            "request": "/v1/mytrades",
            "nonce": self._nonce,
            "currency": 'USD',
            "symbol": symbol,
            "timestamp": timestamp - 24 * 3600,
            "until": timestamp,
            "limit_trades": 300
        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/mytrades", headers=signed_payload, verify=True)
        #r = requests.post(self.URL + "/mytrades", headers=signed_payload, data=payload, verify=True)
        json_resp = r.json()
        return json_resp

    def place_offer(self, currency, amount, rate, period, direction):
        """
        :param currency:
        :param amount:
        :param rate:
        :param period:
        :param direction:
        :return:
        """
        payload = {
            "request": "/v1/offer/new",
            "nonce": self._nonce,
            "currency": currency,
            "amount": amount,
            "rate": rate,
            "period": period,
            "direction": direction
        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/offer/new", headers=signed_payload, verify=True)
        json_resp = r.json()

        return json_resp

    def cancel_offer(self, offer_id):
        """
        :param offer_id:
        :return:
        """
        payload = {
            "request": "/v1/offer/cancel",
            "nonce": self._nonce,
            "offer_id": offer_id
        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/offer/cancel", headers=signed_payload, verify=True)
        json_resp = r.json()

        return json_resp

    def status_offer(self, offer_id):
        """
        :param offer_id:
        :return:
        """
        payload = {
            "request": "/v1/offer/status",
            "nonce": self._nonce,
            "offer_id": offer_id
        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/offer/status", headers=signed_payload, verify=True)
        json_resp = r.json()

        return json_resp

    def active_offers(self):
        """
        Fetch active_offers
        :return:
        """
        payload = {
            "request": "/v1/offers",
            "nonce": self._nonce
        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/offers", headers=signed_payload, verify=True)
        json_resp = r.json()

        return json_resp

    def history_orders(self, limit):
        """
        {
            'id': 8020304272,
            'cid': 7184915920156,
            'cid_date': '2018-02-07',
            'gid': 181720020156,
            'symbol': 'ethbtc',
            'exchange': 'bitfinex',
            'price': '0.1005',
            'avg_execution_price': '0.10044733',
            'side': 'buy',
            'type': 'exchange market',
            'timestamp': '1517971849.0',
            'is_live': False,
            'is_cancelled': False,
            'is_hidden': False,
            'oco_order': None,
            'was_forced': False,
            'original_amount': '0.161',
            'remaining_amount': '0.0',
            'executed_amount': '0.161',
            'src': 'api'
        }

        :return:
        """
        payload = {
            "request": "/v1/orders/hist",
            "nonce": self._nonce,
            "limit": limit
        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/orders/hist", headers=signed_payload, verify=True)
        print(r, r.json())
        json_resp = r.json()

        return json_resp

    def get_our_history_orders(self, limit=1000):
        '''View your latest inactive orders.
            Limited to last 3 days and 1 request per minute.

            用来获取过去成交的orders。

            is_live，is_cancelled， is_hidden，was_forced 都是False的时候，此单是成交单
        '''
        payload = {
            "request": "/v1/orders/hist",
            "nonce": self._nonce,
            "limit": limit
        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/orders/hist", headers=signed_payload, verify=True)
        json_resp = r.json()

        logger.debug('rsp: {}'.format(json_resp))
        res = [e for e in json_resp if ('is_live' in e and 'is_cancelled' in e and 'is_hidden' in e and 'was_forced' in e and not e['is_live'] and not e['is_cancelled'] and not e['is_hidden'] and not e['was_forced'])]
        #return json_resp
        return res

    def balances(self):
        """
        Fetch balances
        :return:
        """
        payload = {
            "request": "/v1/balances",
            "nonce": self._nonce
        }

        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/balances", headers=signed_payload, verify=True)
        json_resp = r.json()

        return json_resp

    def history(self, currency, since=0, until=9999999999, limit=500, wallet='exchange'):
        """
        View you balance ledger entries
        :param currency: currency to look for
        :param since: Optional. Return only the history after this timestamp.
        :param until: Optional. Return only the history before this timestamp.
        :param limit: Optional. Limit the number of entries to return. Default is 500.
        :param wallet: Optional. Return only entries that took place in this wallet. Accepted inputs are: “trading”,
        “exchange”, “deposit”.
        """
        payload = {
            "request": "/v1/history",
            "nonce": self._nonce,
            "currency": currency,
            "since": since,
            "until": until,
            "limit": limit,
            "wallet": wallet
        }
        signed_payload = self._sign_payload(payload)
        r = requests.post(self.URL + "/history", headers=signed_payload, verify=True)
        json_resp = r.json()

        return json_resp

    def get_trades(self):
        '''
        '[{'timestamp': 1514642186, 'tid': 147202633, 'price': '12271.0', 'amount': '0.61956953', 'exchange': 'bitfinex', 'type': 'sell'},' \

        limit_trades 设置1000就会强制成100。暂定设置成500。 返回值得timestamp不是排序好的。所以要筛出最大的保存下来。                                                                                                               ''
        '''

        from_timestamp = 1014886950 # 2002年。获取最近的500条。时间在2018之前就行
        while True:
            timestamps = []
            url = self.base_url + '/v1/trades/{}?timestamp={}&limit_trades={}'.format(self.symbol, from_timestamp, 500)
            rsp = requests.request("GET", url)

            print('rsp: ', rsp.json(), 'symbol: ', self.symbol)
            if isinstance(rsp.json(),  dict) and (('message' in rsp.json() and rsp.json()['message']) == 'Unknown symbol' or rsp.json()['error']):
                time.sleep(2)
                continue

            to_db = []
            for one in rsp.json():

                # 并且timestamp不能等于上次的from_timestamp
                the_timestamp = one['timestamp']
                if the_timestamp == from_timestamp:
                    continue
                timestamps.append(the_timestamp)
                tmp = {
                    '_id': datetime.now(),
                    'tid': one['tid'],
                    'price': one['price'],
                    'amount': one['amount'],
                    'timestamp': one['timestamp'],
                    'type': one['type'],
                }
                to_db.append(tmp)
                time.sleep(0.001)

            if to_db:
                print(len(to_db))
                self.collection.insert(to_db)
                from_timestamp = max(timestamps)

            # 没那么多新trade。睡150秒再获取(前几次分别获取到的，eg: 500->184->66->120。。。)
            time.sleep(150)


if __name__ == '__main__':
    '''
    eth/usd: (0.04)
    btc/usd: (0.002)
    '''
    os.environ[Constants.DQUANT_ENV] = "dev"
    trading = TradingV1('eth_usdt')
    print(trading.getDepth())
    trading.withdraw('ethereum', '0x5d38836532ee39ac341b0549d4290963981dda0b', '0.01')

    # print(trading.delete_order(9058311113))
    #print('past_trades: ', trading.past_trades())
    #print('history: ', trading.history_orders(3))
    #res = trading.get_active_orders()
    #for o in res:
    #    if o["symbol"] == 'ethusd':
    #        print(trading.delete_order(o["id"]))



        #print('balances: ', trading.balances())
    #trading = TradingV1('eth_usd')
    #with open("hist_order.txt", 'w') as data:
    #    res = trading.history_orders(limit=500000)
    #    data.write(str(res))

    #print('new orders', trading.place_order('0.04', '15000', 'sell', 'exchange market', symbol= 'ethusd'))
    #print('new orders', trading.place_order('0.001', '15000', 'sell', 'exchange market', symbol= 'btcusd'))
    #print('new orders', trading.place_order('0.01', '900', 'sell', 'exchange limit', symbol= 'ethusd'))
    #print('active_orders: ', trading.get_active_orders())
    #print('cancel_orders', trading.cancel_active_orders())
