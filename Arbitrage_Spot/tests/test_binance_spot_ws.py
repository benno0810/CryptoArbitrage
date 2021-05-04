import sys
sys.path.append('../')
sys.path.append('../../')
sys.path.append('C:\\Users\\benno\\OneDrive\\Documents\\GitHub\\quantFuckCoin-master')
import os
import unittest
import time
import asyncio

from dquant.constants import Constants
from dquant.markets._binance_spot_rest import Binance
from dquant.markets._binance_spot_ws import BinanceSpotWs
import logging
#logger = logging.getLogger('websockets')
#logger.setLevel(logging.DEBUG)
#logger.addHandler(logging.StreamHandler())


class BinanceSpotWsTestSuite(unittest.TestCase):
    """for config test case"""

    @classmethod
    def setUpClass(cls):
        '''
        首先要用rest进行sell和deleteOrder
        '''
        os.environ[Constants.DQUANT_ENV] = "dev"

    # @unittest.skip("skip")
    def test_get_account(self):
        new = asyncio.get_event_loop()
        bi = BinanceSpotWs("eth_btc", new)
        bi.start()

        while True:
            depth = bi.getDepth()
            print(depth)
            time.sleep(1)

    # @unittest.skip("skip")
    def test_get_orders(self):
        time.sleep(5)
        self.bi_rest.deleteOrder(self.orderId)

        orders = self.bi.get_orders()
        print(orders)

    @unittest.skip("skip")
    def test_trade(self):

        new = asyncio.get_event_loop()
        bi = BinanceSpotWs("eth_btc", new)
        bi.start()

        time.sleep(5)

        # bi_rest = Binance('eth_btc')
        res = bi.buy(amount=0.04, price=0.07)
        print(res)
        orderId = res['order_id']
        while True:
            print(bi.getOrder(orderId))
            # print(bi.deleteOrder(orderId))
            time.sleep(2)
        time.sleep(200)

if __name__ == "__main__":
    unittest.main()