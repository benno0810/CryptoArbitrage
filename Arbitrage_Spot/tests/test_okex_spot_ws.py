import os, sys

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
# rootPath = os.path.split(rootPath)[0]
os.sys.path.append(rootPath)
import unittest

import asyncio

import time

import logging

from dquant.constants import Constants
from dquant.markets._okex_spot_ws_v2 import OkexSpotWs


logger = logging.getLogger()
fh = logging.FileHandler('app.log')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)


class OKEXSpotWsTestSuite(unittest.TestCase):
    """for config test case"""

    @classmethod
    def setUpClass(cls):
        os.environ[Constants.DQUANT_ENV] = "dev"

    @unittest.skip("skipping")
    def test_get_account(self):

        new = asyncio.get_event_loop()
        okex = OkexSpotWs("eth_usdt", new)
        okex.start()
        while True:
            print(time.time(), okex.getAccount())
            print(time.time(), okex.getDepth())
            time.sleep(2)

    @unittest.skip("skipping")
    def test_sell(self):
        '''
        :return: {'result': True, 'order_id': 143248483}
        '''
        new = asyncio.get_event_loop()
        okex = OkexSpotWs("eth_btc", new)
        okex.start()

        time.sleep(10)

        result = okex.sell(amount=0.01)
        print(result)
        time.sleep(100)

    @unittest.skip("skipping")
    def test_delete_order(self):
        new = asyncio.get_event_loop()
        okex = OkexSpotWs('eth_usdt', new)
        okex.start()
        time.sleep(5)
        result = okex.buy(price=73)
        print(result)

    @unittest.skip("skipping")
    def test_getAccount(self):
        new = asyncio.get_event_loop()
        okex = OkexSpotWs('eth_usdt', new)
        okex.start()
        time.sleep(5)
        while True:
            result = okex.getAccount(coin=['BTC', 'ETH'])
            print(result)
            time.sleep(2)

    @unittest.skip("skipping")
    def test_get_order(self):
        new = asyncio.get_event_loop()
        okex = OkexSpotWs('eth_btc', new)
        okex.start()
        time.sleep(5)
        # result = okex.sell(amount=0.01)
        # print(result)
        # id = result['order_id']

        result = okex.getOrder(160177046)
        print(result)
        time.sleep(20)

    def test_account_fee(self):
        new = asyncio.get_event_loop()
        okex = OkexSpotWs("eth_usdt", new)
        okex.start()
        acc = okex.getAccount(['btc', 'eth', 'usdt'])
        print(acc)
        res = okex.sell(0.01)
        print(res)
        while True:
            print(okex.getOrder(res['order_id']))
            acc_1 = okex.getAccount(['btc', 'eth', 'usdt'])
            print(acc_1)
            for coin in acc_1:
                if acc_1[coin] != acc[coin]:
                    break
            time.sleep(1)
        acc = acc_1
        print(acc)

        bid0 = okex.getDepth()['bids'][0]['price']
        res = okex.buy(amount=0.02, price=bid0)
        print(res)
        while True:
            print(okex.getOrder(res['order_id']))
            acc_1 = okex.getAccount(['btc', 'eth', 'usdt'])
            print(acc_1)
            for coin in acc_1:
                if acc_1[coin] != acc[coin]:
                    break
            time.sleep(1)
        acc = acc_1
        print(acc)


if __name__ == "__main__":
    unittest.main()