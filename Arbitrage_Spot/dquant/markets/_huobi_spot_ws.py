# -*- coding: utf-8 -*-

import sys
sys.path.append('../../')
import os
import time
import asyncio
import websockets
import gzip
import json
import logging
import hashlib
import threading, queue
import copy

from dquant.config import cfg
from dquant.constants import Constants
from dquant.markets.market import Market
from dquant.markets._huobi_spot_rest import HuobiRest


logger = logging.getLogger(__name__)
from dquant.common.mongo_conn import MongoConnOrder
#from dquant.common.mongo_conn import MongoConn as MongoConnOrder


class HuobiWs(Market):

    def __init__(self, meta_code,loop):
        self.contract_type = None
        market_currency, base_currency, symbol = self.parse_meta(meta_code)
        super().__init__(market_currency, base_currency, meta_code, cfg.get_float_config(Constants.HUOBI_FEE))
        self.apikey = cfg.get_config(Constants.HUOBI_APIKEY)
        self.apisec = cfg.get_config(Constants.HUOBI_APISEC)
        self.loop = loop
        self.symbol = symbol
        self.websocket = None
        self.base_url = 'wss://api.huobi.pro/ws'
        try:
            #self.channel_kline = 'market.{}.kline.60min'.format(self.symbol)
            self.channel_depth = 'market.{}.depth.step0'.format(self.symbol)
            self.channel_trade_detail = 'market.{}.trade.detail'.format(self.symbol)
            self.channel_market_detail = 'market.{}.detail'.format(self.symbol)
        except Exception as e:
            print(e)
        self.q = asyncio.Queue()
        self.kline = None
        self.depth = {}
        self.trade_detail = None
        self.market_detail = None
        self.sub_id = 'id10'  # "id generate by client" 不知道填什么更好
        self.name = 'HuoBiPro'
        self.latency_col = MongoConnOrder().client.latency.api_latency

        loop1 = asyncio.new_event_loop()
        self.hb_rest = HuobiRest(meta_code, loop1)
        self.hb_rest.setDaemon(True)
        self.hb_rest.start()
        self.register_callbacks()

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.keep_connect())
        tasks = [self.ws_handler()]
        self.loop.run_until_complete(asyncio.wait(tasks))

    def register_callbacks(self):
        #self.methods[self.channel_kline] = self.update_kline
        self.methods[self.channel_depth] = self.update_depth
        self.methods[self.channel_trade_detail] = self.update_trade_detail
        self.methods[self.channel_market_detail] = self.update_market_detail

    def buy(self, amount, price=-1):
        return self.hb_rest.buy(amount, price)

    def sell(self, amount, price=-1):
        return self.hb_rest.sell(amount, price)

    def deleteOrder(self, order_id, tillOK=True):
        return self.hb_rest.deleteOrder(order_id, tillOK)

    async def update_kline(self, data_kline):
        self.kline = data_kline
        self.update_flags["kline"] = True

    async def update_depth(self, data_depth):

        latency_data =  copy.deepcopy(data_depth)
        #lat = int(time.time()*1000) - latency_data['ts']
        #self.latency_col.insert({'timestamp': int(time.time()*1000), 'lantency': lat, 'api': 'depth',
        #                 'market': self.name, 'symbol': self.symbol, 'ip': self.ip})

        list_of_ask = self.huobi_depth_format(data_depth['tick'], "asks")
        list_of_bid = self.huobi_depth_format(data_depth['tick'], "bids")
        self.depth = {"asks": list_of_ask, 'bids': list_of_bid}
        self.update_flags["depth"] = True

    async def update_trade_detail(self, data_trade_detail):
        self.trade_detail = data_trade_detail
        self.update_flags["trade_detail"] = True

    async def update_market_detail(self, data_market_detail):
        self.market_detail = data_market_detail
        self.update_flags['market_detail'] = True

    def huobi_depth_format(self, res, flag):
        '''格式化ws传回数据'''

        result_list = []
        for ticker in res[flag]: result_list.append({
                'price': float(ticker[0]),
                'amount': float(ticker[1])
            })

        if flag == "asks":  # 卖单从小到大
            result_list.sort(key=lambda x: x['price'])
        else:  # 买单从大到小
            result_list.sort(key=lambda x: x['price'], reverse=True)
        return result_list

    def update(self, flags):
        '''
        :param flags: {"depth": True, 'trade': False}
        :return:
        '''
        self.unset_flags(flags)
        #self.register_callbacks()

        while True:
            asyncio.sleep(1)
            if (self.check_flags(flags)):
                break
        return self

    def buildMySign(self, params, secretKey):
        sign = ''
        for key in sorted(params.keys()):
            sign += key + '=' + str(params[key]) + '&'
        return hashlib.md5((sign + 'secret_key=' + secretKey).encode("utf-8")).hexdigest().upper()

    def parse_meta(self, meta_code):
        meta_table = {'eth_usdt': ("eth", "usdt", "ethusdt"),
                      'btc_usdt': ("btc", "usdt", "btcusdt"),
                      'eth_btc': ("eth", "btc", "ethbtc"),
                      'ltc_eth': ('ltc', 'eth', 'ltceth'),
                      'bch_usdt': ('bch', 'usdt', 'bchusdt'),
                      'ven_eth': ('ven', 'eth', 'veneth'),
                      'bch_eth': ('bch', 'eth', 'bcheth'),
                      'bch_btc': ('bch', 'btc', 'bchbtc'),
                      'ltc_btc': ('ltc', 'btc', 'ltcbtc'),
                      'ltc_usdt': ('ltc', 'usdt', 'ltcusdt'),
                      'eos_eth': ('eos', 'eth', 'eoseth'),
                      'eos_btc': ('eos', 'btc', 'eosbtc'),
                      }
        return meta_table[meta_code]

    def build_message(self, channel, event='addChannel', **kwargs):
        '''
        :param channel: subscribe channel
        :param event: default 'addChannel'
        :param kwargs: parameters
        '''

        params = {'api_key': self.apikey}

        params['sign'] = self.buildMySign(params, self.apisec)
        message = str({'event': event, 'sub': channel, 'parameters': params})
        return message

    async def sub_channel(self):
        '''初始已经订阅了kline, depth, trade_detail'''
        #message_kline = json.dumps({'id': self.sub_id, 'sub': self.channel_kline})
        message_depth = json.dumps({'id': self.sub_id, 'sub': self.channel_depth})
        message_trade_detail = json.dumps({'id': self.sub_id, 'sub': self.channel_trade_detail})
        message_market_detail = json.dumps({'id': self.sub_id, 'sub': self.channel_market_detail})
        #await self.websocket.send(message_kline)
        await self.websocket.send(message_depth)
        await self.websocket.send(message_trade_detail)
        await self.websocket.send(message_market_detail)

    async def ws_init(self):
        await self.sub_channel()

    #async def send(self):
    #    # 等待登录
    #    await asyncio.sleep(1)
    #    while True:
    #        message = await self.q.get()
    #        await self.websocket.send(message)

    async def ws_handler(self):
        '''
        handle task in backthread
        :return:
        '''
        while True:
            compressData = await self.websocket.recv()
            result = gzip.decompress(compressData).decode('utf-8')
            result = json.loads(result)
            if "ping" in result:
                pong=json.dumps({"pong": result["ping"]})
                await self.websocket.send(pong)
            elif 'ch' in result:
                await self.methods[result['ch']](result)

    def get_kline(self):
        self.update({'kline': False})
        return self.kline

    def get_depth(self):
        s_time = time.time()
        ret = dict(bids=[], asks=[])
        self.update({"depth": False})
        if not self.depth:
            self.compute_latency(s_time, 'depth')
            return ret
        self.update({"depth": False})
        kinds = ['bids', 'asks']
        for k in kinds:
            for one in self.depth[k]:
               ret[k].append({'price': one['price'], 'amount': one['amount']})

        ret['bids'].sort(key=lambda item: item['price'], reverse=True)
        ret['asks'].sort(key=lambda item: item['price'], reverse=False)
        self.compute_latency(s_time, 'depth')
        return ret

    def get_trade_detail(self):
        self.update({"trade_detail": False})
        return self.trade_detail

    def get_market_detail(self):
        self.update({"market_detail": False})
        return self.market_detail


if __name__ == '__main__':

    #test_bitfinex_spot_ws()
    #os._exit(0)

    os.environ[Constants.DQUANT_ENV] = "dev"
    loop = asyncio.get_event_loop()
    hb = HuobiWs('eth_btc', loop)
    hb.setDaemon(True)
    hb.start()

    while True:
        print(hb.get_depth())
        time.sleep(2)
    # print(hb.get_trade_detail())
    # print(hb.get_market_detail())

    time.sleep(200)
