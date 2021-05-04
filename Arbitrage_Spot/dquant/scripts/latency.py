import asyncio
import threading
import time
import os


curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
rootPath = os.path.split(rootPath)[0]
os.sys.path.append(rootPath)

from dquant.constants import Constants
from dquant.markets._binance_spot_ws import BinanceSpotWs
from dquant.markets._huobi_spot_rest import HuobiRest
from dquant.markets._okex_spot_ws import OkexSpotWs
from dquant.markets._bitfinex_spot_ws import BitfinexSpotWs

mkts = [BinanceSpotWs, HuobiRest, OkexSpotWs, BitfinexSpotWs]
# mkts = [HuobiRest, OkexSpotWs, BitfinexSpotWs]


class MyMarket(threading.Thread):
    def __init__(self, mkt, meta_code="eth_btc"):
        super().__init__()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.mkt = mkt(meta_code=meta_code, loop=self.loop)
        self.name = self.mkt.name
        self.mkt.setDaemon(True)
        self.mkt.start()
        self.order_id = None
        time.sleep(15)

    def run(self):
        pass

    def getDepth(self):
        self.mkt.getDepth()

    def getAccount(self):
        self.mkt.getAccount(coin=[self.mkt.base_currency, self.mkt.market_currency])

    def buy(self):
        result = self.mkt.buy(amount=0.04, price=0.09)
        self.order_id = result['order_id']

    def getOrder(self):
        self.mkt.getOrder(self.order_id)

    def deleteOrder(self):
        self.mkt.deleteOrder(self.order_id)



os.environ[Constants.DQUANT_ENV] = "dev"
test_objs = {}
for mkt in mkts:
    obj = MyMarket(mkt)
    obj.start()
    obj.getDepth()
    obj.getAccount()
    obj.buy()
    obj.getOrder()
    obj.deleteOrder()


# loop = asyncio.get_event_loop()
# hb = HuobiRest(loop=loop, meta_code="eth_btc")
# hb.start()
# time.sleep(15)
# hb.getDepth()
# hb.getAccount(coin=[hb.base_currency, hb.market_currency])
# result = hb.buy(amount=0.04, price=0.09)
# order_id = result['order_id']
# hb.getOrder(order_id)
# hb.deleteOrder(order_id)
