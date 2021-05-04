import os

from dquant.constants import Constants
from dquant.common.mongo_conn import MongoConnOrder


'''
bch_btc
bch_eth
btc_usdt
eos_btc
eos_eth
eth_btc
eth_usdt
'''

ips = ['172.31.18.172', '172.31.22.135']
mkts = ['HuoBiPro', 'OKEX', 'Bitfinex']
apis = ['buy', 'cancel', 'depth']
symbols = ['bch_btc', 'bch_eth', 'btc_usdt', 'eos_btc', 'eos_eth', 'eth_btc', 'eth_usdt', 'bchbtc', 'bcheth', 'btcusdt', 'eosbtc', 'eoseth', 'ethbtc', 'ethusdt',
           'tBCHBTC', 'tBCHETH', 'tBTCUSDT', 'tEOSBTC', 'tEOSETH', 'tETHBTC', 'tETHUSDT']

def get_unit(market, api, symbol):

    lat = MongoConnOrder().client.latency.api_latency
    res = lat.find_one({'market': market, 'api': api, 'symbol': symbol})
    return res


def get_latency_data():

    dic = {}

    global ips, mkts, apis, symbols

    for ip in ips:
        dic[ip] = {}
        for m in mkts:
            dic[ip][m] = {}
            for a in apis:
                dic[ip][m][a] = {}
                for s in symbols:
                    res = get_unit(m, a, s)
                    if res:
                        dic[ip][m][a][s] = res['lantency']

    print('dic: ', dic)

if __name__ == '__main__':
    os.environ[Constants.DQUANT_ENV] = "pro"
    get_latency_data()