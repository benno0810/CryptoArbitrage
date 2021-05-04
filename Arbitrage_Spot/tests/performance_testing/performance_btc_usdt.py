import sys
sys.path.append('../')
sys.path.append('../../')
import os
import time
import asyncio

from dquant.constants import Constants
from dquant.markets._binance_spot_rest import Binance
from dquant.markets._huobi_spot_ws import HuobiWs
from dquant.markets._bitfinex_spot_ws import BitfinexSpotWs
from dquant.markets._okex_spot_ws_v2 import OkexSpotWs
from tests.performance_testing.performance_common import Performance


class BtcUsdtWithoutLoop(Performance):

    def __init__(self, Market):
        os.environ[Constants.DQUANT_ENV] = "dev"
        self.mkt = Market("btc_usdt")
        self.mkt.setDaemon(True)
        self.mkt.start()
        time.sleep(10)
        super().__init__(self.mkt)

    def buy(self):
        res_b = self.mkt.buy(0.01, price=2000)
        return res_b


class BtcUsdtWithLoop(Performance):

    def __init__(self, Market):
        os.environ[Constants.DQUANT_ENV] = "dev"
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.mkt = Market("btc_usdt", loop)
        self.mkt.setDaemon(True)
        self.mkt.start()
        time.sleep(10)
        super().__init__(self.mkt)

    def buy(self):
        res_b = self.mkt.buy(0.01, price=2000)
        return res_b


class OkexBtcUsdtWithLoop(Performance):

    def __init__(self, Market):
        os.environ[Constants.DQUANT_ENV] = "dev"
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.mkt = Market("btc_usdt", loop)
        self.mkt.setDaemon(True)
        self.mkt.start()
        time.sleep(10)
        super().__init__(self.mkt)

    def buy(self):
        res_b = self.mkt.buy(2000, amount=0.01)
        return res_b


def test_bi():
    bi = BtcUsdtWithoutLoop(Binance)
    bi.run()


def test_bi_huobi_bfx_okex():
    bi = BtcUsdtWithoutLoop(Binance)
    bi.setDaemon(True)

    hb_ws = BtcUsdtWithLoop(HuobiWs)
    hb_ws.setDaemon(True)

    bfx = BtcUsdtWithLoop(BitfinexSpotWs)
    bfx.setDaemon(True)

    okex = OkexBtcUsdtWithLoop(OkexSpotWs)
    okex.setDaemon(True)

    for mkt in [bi, hb_ws, bfx, okex]:
        mkt.start()

    for mkt in [bi, hb_ws, bfx, okex]:
        mkt.join()

if __name__ == '__main__':
    os.environ[Constants.DQUANT_ENV] = "dev"
    test_bi_huobi_bfx_okex()
