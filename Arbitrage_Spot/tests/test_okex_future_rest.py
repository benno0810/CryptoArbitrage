import unittest,time

import os

from dquant.constants import Constants
from dquant.markets._okex_future_rest import OkexFutureRest


class OKEXFutureRestTestSuite(unittest.TestCase):
    """for config test case"""

    @classmethod
    def setUpClass(cls):
        os.environ[Constants.DQUANT_ENV] = "dev"

    @unittest.skip("skipping test_get_ticker")
    def test_get_ticker(self):
        ticker = OkexFutureRest("eth_usd_this_week").get_ticker()
        print(ticker)
        return ticker

    # @unittest.skip("skipping test_get_depth")
    def test_get_depth(self):
        while True:
            depth = OkexFutureRest("btc_usd_this_week").get_depth()
            print(depth)
            time.sleep(0.5)

    @unittest.skip("skipping long")
    def test_long(self):
        ok = OkexFutureRest("eth_usd_this_week")
        ticker = ok.get_ticker()
        price = ticker['bid']['price']
        res = OkexFutureRest("eth_usd_this_week").long(amount=1, price=price)
        print(res)

    @unittest.skip("skipping short")
    def test_short(self):
        ok = OkexFutureRest("eth_usd_this_week")
        ticker = ok.get_ticker()
        price = ticker['ask']['price']
        res = OkexFutureRest("eth_usd_this_week").short(amount=1, price=price)
        print(res)

    @unittest.skip("skipping")
    def test_close_long(self):
        ok = OkexFutureRest("eth_usd_this_week")
        res = OkexFutureRest("eth_usd_this_week").close_long(amount=1)
        print(res)

    @unittest.skip("skipping")
    def test_close_short(self):
        ok = OkexFutureRest("eth_usd_this_week")
        res = OkexFutureRest("eth_usd_this_week").close_short(amount=1)
        print(res)

    @unittest.skip("skipping")
    def test_delete_order(self):
        ok = OkexFutureRest("eth_usd_this_week")
        # 尽可能不成交的价格
        p = ok.get_depth()['asks'][-1]['price']
        res = ok.short(amount=1, price=p, lever_rate=15)
        print(res)
        id = res["order_id"]
        res = ok.delete_order(order_id=id)
        print(res)

    @unittest.skip("skipping")
    def test_get_account(self):
        ok = OkexFutureRest("eth_usd_this_week")
        print(ok.get_account())

if __name__ == '__main__':
    unittest.main()
