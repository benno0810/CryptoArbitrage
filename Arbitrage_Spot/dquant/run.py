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

meta_binance = ['eth_usdt', 'btc_usdt', 'eth_btc', 'eos_eth', 'bcc_eth']
meta_bfx = ['eth_btc']
meta_huobi = ['eth_usdt', 'eth_btc', 'eos_eth']
meta_ok = ['eth_usdt', 'eth_btc', 'btc_usdt', 'eos_eth', 'bch_eth']
meta_ok_symbol = ['btc_usd', 'eth_usd']
meta_ok_future_to_spot = {'btc_usd': 'btc_usdt', 'eth_usd': 'eth_usdt'}
meta_ok_contract = ['this_week', 'next_week', 'quarter']
# meta_ok_future = [s+'_'+c for s in meta_ok_symbol for c in meta_ok_contract]

os.environ[Constants.DQUANT_ENV] = "dev"
dlogger = init_roll_log('cancel_order.log')

logger = logging.getLogger("dquant")

okex_last_open_long_timestamp = None


def sucess_fail_record(platform, res):
    if res['success']:
        dlogger.info('{}: cancel {} sucessfuly'.format(platform, res['success']))
    if res['fail']:
        dlogger.info('{}: cancel {} failed'.format(platform, res['fail']))


@app.route('/cancel/binance/active_orders/get', methods=['GET'])
def get_binance_active_orders():
    res = []
    for meta_code in meta_binance:
        bi = Binance(meta_code)
        tmp = bi.get_active_orders()
        if 'code' in tmp and 'msg' in tmp:
            continue
        res.extend(bi.get_active_orders())
    return jsonify(res)


@app.route('/cancel/binance/active_orders/del', methods=['DELETE'])
def del_binance_active_orders():
    res = {'result': True, 'success': [], 'fail': []}
    for meta_code in meta_binance:
        bi = Binance(meta_code)
        tmp = bi.cancel_active_orders()
        res['success'].extend(tmp['success'])
        res['fail'].extend(tmp['fail'])
    sucess_fail_record('binance', res)
    return jsonify(res)


@app.route('/cancel/bfx/active_orders/get', methods=['GET'])
def get_bfx_active_orders():
    res = []
    for meta_code in meta_bfx:
        bfx = TradingV1(meta_code)
        res.extend(bfx.get_active_orders())
    return jsonify(res)


@app.route('/cancel/bfx/active_orders/del', methods=['DELETE'])
def del_bfx_active_orders():
    res = {'result': True}
    for meta_code in meta_bfx:
        bfx = TradingV1(meta_code)
        tmp = bfx.cancel_active_orders()
        print('tmp:', tmp)
        if tmp['result'] == 'None to cancel':
            continue
        else:
            dlogger.debug('bfx cancel result: {}'.format(res))
            return jsonify(res)
    res['result'] = False

    return res


@app.route('/cancel/huobi/active_orders/get', methods=['GET'])
def get_huobi_active_orders():

    res = []
    loop = asyncio.new_event_loop()
    for meta_code in meta_huobi:
        hb = HuobiRest(meta_code, loop)
        res.extend(hb.get_activate_orders())
    return jsonify(res)


@app.route('/cancel/huobi/active_orders/del', methods=['DELETE'])
def del_huobi_active_orders():

    res = {'result': True, 'success': [], 'fail': []}
    loop = asyncio.new_event_loop()
    for meta_code in meta_huobi:
        hb = HuobiRest(meta_code, loop)
        tmp = hb.cancel_active_orders().get('data', {})
        if tmp:
            res['success'].extend(tmp['success'])
            res['fail'].extend(tmp['failed'])

    sucess_fail_record('huobi', res)
    return jsonify(res)


@app.route('/cancel/okex/active_orders/get', methods=['GET'])
def get_okex_active_orders():

    res = []
    for meta_code in meta_ok:
        ok = OkexSpotRest(meta_code)
        res.extend(ok.get_active_orders())
    return jsonify(res)


@app.route('/cancel/okex/active_orders/del', methods=['DELETE'])
def del_okex_active_orders():
    '''
    :return: {'success': [1,23], 'fail': [4]}
    '''
    res = {'result': True, 'success': [], 'fail': []}
    for meta_code in meta_ok:
        ok = OkexSpotRest(meta_code)
        tmp = ok.cancel_active_orders()

        if 'success' in tmp:
            res['success'].extend(tmp['success'].split(','))
            res['fail'].extend(tmp['error'].split(','))
        elif 'result' in tmp:
            if tmp['result']:
                res['success'].append(tmp['order_id'])
            else:
                res['fail'].append(tmp['order_id'])

    sucess_fail_record('okex', res)
    return jsonify(res)

#
# @app.route('/cancel/okex_future/active_orders/get/<symbol>', methods=['GET'])
# def get_okexf_active_orders(symbol):
#     # res_all = {}
#     res = {'active_orders':[],
#            'positions':[],
#            'force_liqu_price':'',
#            'spot_price': 0,
#            'future_index': 0,
#            'premiums_and_discounts': 0,
#            'timestamp': int(time.time())}
#     if symbol not in meta_ok_symbol:
#         return jsonify(res)
#     ok_f_index = OkexFutureRest(symbol+'_'+ 'this_week')
#     ret_index = ok_f_index.get_index()
#     ok_spot = OkexSpotRest(meta_ok_future_to_spot[symbol])
#     ret_ticker = ok_spot.get_ticker()
#     for meta_contract in meta_ok_contract:
#         real_meta = symbol+'_'+ meta_contract
#         # res = {'active_orders': [], 'positions': [], 'force_liqu_price': ''}
#         ok_f = OkexFutureRest(real_meta)
#         # res.extend(ok_f.get_active_orders())
#         res['active_orders'].extend(ok_f.get_active_orders())
#         ret_position = ok_f.getPosition()
#         if ret_position and ret_ticker and ret_index:
#             res['force_liqu_price'] = ret_position['force_liqu_price']
#             # res_all[meta_code] = res
#             res['spot_price'] = float(ret_ticker['ticker']['last'])
#             res['timestamp'] = int(ret_ticker['date'])
#             res['future_index'] = float(ret_index['future_index'])
#             premiums_and_discounts = float(res['future_index'] - res['spot_price'])
#             res['premiums_and_discounts'] = premiums_and_discounts
#             if ret_position['holding']:
#                 for holding in ret_position['holding']:
#                     long_prifit_and_loss = 0.0
#                     if not holding['buy_available']:
#                         holding.update({"long_prifit_and_loss": long_prifit_and_loss})
#                     else:
#                         buy_available = float(holding['buy_available'])
#                         buy_price_avg = float(holding['buy_price_avg'])
#                         print(buy_available, buy_price_avg)
#                         long_prifit_and_loss = premiums_and_discounts * buy_available * 100 / buy_price_avg
#                         holding.update({"long_prifit_and_loss": long_prifit_and_loss})
#             res['positions'].extend(ret_position['holding'])
#     return jsonify(res)
#     # return jsonify(res_all)
#
# @app.route('/cancel/okex_future/active_orders/del/<symbol>/long', methods=['DELETE'])
# def close_okexf_long_orders(symbol):
#     # 分三步：1.取消未完成订单 2.平仓 3.补回现货
#     res = {'result': False, 'success': [], 'fail': [], 'spot_results':[], 'msg':''}
#     if symbol not in meta_ok_symbol:
#         res['msg'] = u"暂不支持此类合约"
#         return jsonify(res)
#     spot_balance = OkexSpotRest(meta_ok_future_to_spot[symbol]).get_buy_balance_for_future()
#     for meta_contract in meta_ok_contract:
#         real_meta = symbol + '_' + meta_contract
#         ok = OkexFutureRest(real_meta)
#         ret_position = ok.getPosition()
#         buy_available = 0
#         if ret_position and 'holding' in ret_position:
#             for holding in ret_position['holding']:
#                 buy_available += holding['buy_available']
#         if spot_balance < buy_available*100:
#             res['msg'] += u"现货账户余额不足：%s usdt; " % spot_balance
#             return jsonify(res)
#         ok.cancel_all_orders()
#         result = ok.close_all_long_orders()
#         res['success'].extend(result['success'])
#         res['fail'].extend(result['fail'])
#         price_to_be_buy_spot = float(result['success_amount']) * 100
#         logger.info("price_to_be_buy_spot: %s" % price_to_be_buy_spot)
#         if price_to_be_buy_spot:
#             # spot_balance = OkexSpotRest(meta_ok_future_to_spot[symbol]).get_buy_balance_for_future()
#             # if spot_balance < price_to_be_buy_spot:
#             #     res['msg'] += u"现货账户余额不足：%s usdt; " % spot_balance
#             #     return jsonify(res)
#             ok_spot = OkexSpotRest(meta_ok_future_to_spot[symbol])
#             spot_result = ok_spot.buy_step_by_step(price_to_be_buy_spot, 10)
#             logger.info("flask %s price_to_be_buy_spot result: %s" % (meta_ok_future_to_spot[symbol], spot_result))
#             res['spot_results'] = spot_result
#         res['result'] = True
#     return jsonify(res)
#
# @app.route('/cancel/okex_future/active_orders/del/<symbol>/short', methods=['DELETE'])
# def close_okexf_short_orders(symbol):
#     res = {'result': True, 'success': [], 'fail': [], 'msg':''}
#     if symbol not in meta_ok_symbol:
#         res['msg'] = u"暂不支持此类合约"
#         return jsonify(res)
#     for meta_contract in meta_ok_contract:
#         real_meta = symbol + '_' + meta_contract
#         ok = OkexFutureRest(real_meta)
#         result = ok.close_all_short_orders()
#         res['success'].extend(result['success'])
#         res['fail'].extend(result['fail'])
#     return jsonify(res)
#
#
# @app.route('/cancel/okex_future/open_position/<symbol>/<contract>/<amount>', methods=['get'])
# def open_okexf_long_orders_get(symbol, contract, amount):
#     res = {'result': False, 'msg': ''}
#     now = time.time()
#     global okex_last_open_long_timestamp
#     if okex_last_open_long_timestamp and now - okex_last_open_long_timestamp <= 1:
#         logger.error("Double click: now: %s, last: %s" % (now, okex_last_open_long_timestamp))
#         res['msg'] = u"请不要在1秒内多次点击开仓"
#         return jsonify(res)
#     okex_last_open_long_timestamp = now
#     symbol_map = {'btc_usd': 'btc_usdt', 'eth_usd':'eth_usdt'}
#     symbol = symbol
#     contract = contract
#     amount = amount
#     if not (symbol in meta_ok_symbol and contract in meta_ok_contract and amount):
#         res['msg'] = u"暂不支持此类合约"
#         return jsonify(res)
#     else:
#         spot_balance_base = OkexSpotRest(symbol_map[symbol]).get_sell_balance_for_future()
#         if spot_balance_base < float(amount) * 100:
#             res['msg'] = u"现货账户余额不足：%s usdt" % spot_balance_base
#             return jsonify(res)
#         real_future_meta = symbol + '_' + contract
#         Process(target=create_hedging_process, args=(float(amount), real_future_meta, symbol_map[symbol],)).start()
#         # okexHedge = Hedging(float(amount), real_future_meta, symbol_map[symbol])
#         # okexHedge.setDaemon(True)
#         # okexHedge.start()
#         res['msg'] = u"成功"
#         res = {'result': True}
#     return jsonify(res)


@app.route('/cancel/history/binance/orders', methods=['GET'])
def binance_history_orders_get():

    logger.debug('{} called at {}'.format(sys._getframe().f_code.co_name, datetime.now()))

    bi = Binance('eth_usdt')
    res = bi.get_our_history_orders()
    return jsonify(res)


@app.route('/cancel/history/bitfinex/orders', methods=['GET'])
def bitfinex_history_orders_get():

    logger.debug('{} called at {}'.format(sys._getframe().f_code.co_name, datetime.now()))

    bfx = TradingV1('eth_usdt')
    res = bfx.get_our_history_orders()
    return jsonify(res)


@app.route('/cancel/history/huobi/orders', methods=['GET'])
def huobi_history_orders_get():

    logger.debug('{} called at {}'.format(sys._getframe().f_code.co_name, datetime.now()))

    loop = asyncio.new_event_loop()
    hb = HuobiRest('eth_usdt', loop)
    res = hb.get_our_history_orders()
    return jsonify(res)


# @app.route('/cancel/okex_future/open_position', methods=['POST'])
# def open_okexf_long_orders():
#     res = {'result': False}
#     symbol_map = {'btc_usd': 'btc_usdt', 'eth_usd':'eth_usdt'}
#     symbol = request.form.get('symbol', '')
#     contract = request.form.get('contract', '')
#     amount = request.form.get('amount', 0.0)
#     if not (symbol in meta_ok_symbol and contract in meta_ok_contract and amount):
#         return jsonify(res)
#     else:
#         real_future_meta = symbol + '_' + contract
#         okexHedge = Hedging(float(amount), real_future_meta, symbol_map[symbol])
#         # okexHedge.setDaemon(True)
#         okexHedge.start()
#         res = {'result': True}
#     return jsonify(res)

if __name__ == "__main__":
    os.environ[Constants.DQUANT_ENV] = "dev"
    port = int(sys.argv[1]) if len(sys.argv) >= 2 else 5000
    app.run(host='0.0.0.0', port=port)
