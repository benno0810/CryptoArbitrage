import logging

from dquant.markets._bitmex_future_ws import BitmexFutureWs
from dquant.markets._okex_future_ws import OkexFutureWs


def create_markets(exchangeNames):
    markets = {}
    for name in exchangeNames:
        if (name == 'bitmex_future_btcusd'):
            exchange = BitmexFutureWs('btc_usd')
        elif (name == 'okex_future_btcusd_thisweek'):
            exchange = OkexFutureWs('btc_usd_this_week')
        exchange.name = name
        logging.info('%s market initialized' % (exchange.name))
        exchange.update()
        markets[name] = exchange
    return markets
