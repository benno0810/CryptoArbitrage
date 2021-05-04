import sys
sys.path.append('../')
sys.path.append('../../')
import os
import time
import asyncio

from dquant.constants import Constants
from dquant.markets._binance_spot_rest import Binance
from dquant.markets._huobi_spot_rest import HuobiRest
from dquant.markets._bitfinex_spot_ws import BitfinexSpotWs
from dquant.markets._okex_spot_ws_v2 import OkexSpotWs
from tests.performance_testing.performance_common import PerformanceGetAccount


class BchBtcWithoutLoop(PerformanceGetAccount):

    def __init__(self, Market, sysmbol = 'btc_usdt'):
        os.environ[Constants.DQUANT_ENV] = "dev"
        self.mkt = Market(sysmbol)
        self.mkt.setDaemon(True)
        self.mkt.start()
        time.sleep(20)
        super().__init__(self.mkt)


class BchBtcWithLoop(PerformanceGetAccount):

    def __init__(self, Market):
        os.environ[Constants.DQUANT_ENV] = "dev"
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.mkt = Market("btc_usdt", loop)
        self.mkt.setDaemon(True)
        self.mkt.start()
        time.sleep(20)
        super().__init__(self.mkt)



class OkexBchBtcWithLoop(PerformanceGetAccount):

    def __init__(self, Market):
        os.environ[Constants.DQUANT_ENV] = "dev"
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.mkt = Market("btc_usdt", loop)
        self.mkt.setDaemon(True)
        self.mkt.start()
        time.sleep(20)
        super().__init__(self.mkt)


def test_bi_huobi_bfx_okex():

    bi = BchBtcWithoutLoop(Binance)
    bi.setDaemon(True)

    hb = BchBtcWithLoop(HuobiRest)
    hb.setDaemon(True)

    bfx = BchBtcWithLoop(BitfinexSpotWs)
    bfx.setDaemon(True)

    okex = OkexBchBtcWithLoop(OkexSpotWs)
    okex.setDaemon(True)

    bi.start()
    hb.start()
    bfx.start()
    okex.start()

    bi.join()
    hb.join()
    bfx.join()
    okex.join()


if __name__ == '__main__':
    os.environ[Constants.DQUANT_ENV] = "dev"
    test_bi_huobi_bfx_okex()