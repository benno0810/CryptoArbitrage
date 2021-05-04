import asyncio
import os, time
import unittest
from concurrent.futures import ProcessPoolExecutor
from dquant.constants import Constants
from dquant.markets._bitfinex_spot_ws import BitfinexSpotWs


class BitfinexFutureRestTestSuite(unittest.TestCase):
    """for config test case"""

    @classmethod
    def setUpClass(cls):
        os.environ[Constants.DQUANT_ENV] = "dev"

    @unittest.skip("skip")
    def test_get_depth_background(self):
        new = asyncio.get_event_loop()
        bfx = BitfinexSpotWs("eth_usd",new)
        bfx.start()
        while True:
            x = bfx.getDepth()
            time.sleep(5)
            print(x)

    @unittest.skip("skip")
    def test_get_account(self):
        new = asyncio.get_event_loop()
        bfx = BitfinexSpotWs("eth_usd", new)
        bfx.start()
        time.sleep(10)
        x = bfx.get_account(coin=['BTC', 'ETH', 'USD'])
        print(x)


    @unittest.skip("skip")
    def test_trade(self):
        new = asyncio.get_event_loop()
        bfx = BitfinexSpotWs("eth_usd", new)
        bfx.start()
        time.sleep(5)
        print('buy', bfx.buy(amount=0.04))
        time.sleep(200)

    @unittest.skip("skip")
    def test_get_order(self):
        new = asyncio.new_event_loop()
        okex = OkexFutureWs("btc_usd_this_week", new)
        okex.start()
        # print(okex.get_order(order_id=123))

    # @unittest.skip("skip")
    def test_delete_order(self):
        # new = asyncio.new_event_loop()
        new = asyncio.get_event_loop()
        bfx = BitfinexSpotWs("eth_usd", new)
        bfx.start()
        result = bfx.sell(amount=0.04)
        print(result)

        time.sleep(500)


if __name__ == '__main__':
    unittest.main()
