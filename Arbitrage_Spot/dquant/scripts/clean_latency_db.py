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

from dquant.common.mongo_conn import MongoConnOrder


def remove_old_data():

    lat = MongoConnOrder().client.latency.api_latency
    ts = int(time.time()*1000) - 60000

    print(lat.count())
    lat.delete_many({'timestamp': {'$lt': ts}, 'api': 'depth'})
    print(lat.count())


if __name__ == '__main__':
    os.environ[Constants.DQUANT_ENV] = "pro"
    while True:
        remove_old_data()
