import os

import time
from datetime import datetime

import logging
from flask import Flask
from flask import jsonify
import asyncio
import sys

from flask import request
from multiprocessing import Process

sys.path.append('../')
sys.path.append('../../')
sys.path.append('../strategy/')
from dquant.markets._binance_spot_rest import Binance
from dquant.markets._bitfinex_spot_rest import TradingV1
from dquant.markets._huobi_spot_rest import HuobiRest
from dquant.markets._okex_spot_rest import OkexSpotRest
from dquant.constants import Constants
from dquant.common.depth_log import init_roll_log
from flask_cors import *

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
CORS(app, supports_credentials=True)

meta_binance = ['eth_usdt', 'btc_usdt', 'eth_btc']
meta_bfx = ['eth_btc']
meta_huobi = ['eth_usdt', 'eth_btc']
meta_ok = ['eth_usdt', 'eth_btc', 'btc_usdt']
meta_ok_symbol = ['btc_usd', 'eth_usd']
meta_ok_future_to_spot = {'btc_usd': 'btc_usdt', 'eth_usd': 'eth_usdt'}
meta_ok_contract = ['this_week', 'next_week', 'quarter']

os.environ[Constants.DQUANT_ENV] = "dev"
dlogger = init_roll_log('cancel_order.log')

logger = logging.getLogger("run_history_orders.log")


@app.route('/history/binance/orders', methods=['get'])
def binance_history_orders_get():

    logger.debug('{} called at {}'.format(sys._getframe().f_code.co_name, datetime.now()))

    bi = Binance('eth_usdt')
    res = bi.get_our_history_orders()
    return jsonify(res)


@app.route('/history/bitfinex/orders', methods=['get'])
def bitfinex_history_orders_get():

    logger.debug('{} called at {}'.format(sys._getframe().f_code.co_name, datetime.now()))

    bfx = TradingV1('eth_usdt')
    res = bfx.get_our_history_orders()
    return jsonify(res)


@app.route('/history/huobi/orders', methods=['get'])
def huobi_history_orders_get():

    logger.debug('{} called at {}'.format(sys._getframe().f_code.co_name, datetime.now()))

    loop = asyncio.new_event_loop()
    hb = HuobiRest('eth_usdt', loop)
    res = hb.get_our_history_orders()
    return jsonify(res)


if __name__ == "__main__":
    os.environ[Constants.DQUANT_ENV] = "dev"
    port = int(sys.argv[1]) if len(sys.argv) >= 2 else 2017
    app.run(host='0.0.0.0', port=port)
