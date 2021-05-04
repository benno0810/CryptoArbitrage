import json
from pprint import pprint

import os

from dquant.constants import Constants
from dquant.markets._huobi_spot_rest import HuobiRest

os.environ[Constants.DQUANT_ENV] = "dev"

class TxtParser(object):
    def __init__(self, file):
        # btc, eth, eos, bch, usdt
        self.profit = [0,0,0,0,0]
        self.vol = [0,0,0,0,0]
        self.fee = [0,0,0,0,0]
        self.net_profit = [0,0,0,0,0]
        self.file = file

    @staticmethod
    def dict_add(d1, d2):
        ret = {}
        for i in d1:
            ret[i] = d1[i] + d2[i]
        return ret

    def load_txt(self):
        with open(self.file) as f:
            for i in f.readlines():
                vol = i.split(";")[1]
                profit = i.split(";")[3].split("profit:")[-1]
                fee = i.split(";")[4].split("fee:")[-1][:-2]

                vol_l = eval(vol)
                prof_l = eval(profit)
                fee_l = eval(fee)

                for i in range(5):
                    self.profit[i] += float(prof_l[i])
                    self.vol[i] += float(vol_l[i])
                    self.fee[i] += float(fee_l[i])

        for i in range(5):
            self.net_profit[i] = self.profit[i] -self.fee[i]

    def print_result(self):
        print("Vol.:", self.vol)
        print("Prof.:", self.profit)
        print("Fee:", self.fee)
        print("Net Prof.:", self.net_profit)


class JsonParser(object):
    def __init__(self, file):
        self.file = file
        self.d = {}
        self.load_json()

    def dict_add(self, d1, d2):
        ret = {}
        for i in d1:
            ret[i] = d1[i] + d2[i]
        return ret

    def load_json(self):
        self.d = json.load(open(self.file, 'r'))

    def calc_with_price(self, price):
        '''
        :param price: {'ethbtc': 0.0777, 'ethusdt': 724, 'btcusdt': 9565,
             'eoseth':0.008260, 'eosbtc':0.00062677,
             'bcheth':1.53348, 'bchbtc':0.115750}
        :return:
        '''
        profit_data = {}
        check_data = {}
        total = {}
        for date, detail in self.d.items():
            profit_data[date] = {'bchbtc': [False, 0.0],
                                 'bcheth': [False, 0.0],
                                 'btcusdt': [False, 0.0],
                                 'eosbtc': [False, 0.0],
                                 'eoseth': [False, 0.0],
                                 'ethbtc': [False, 0.0],
                                 'ethusdt': [False, 0.0]}
            check_data[date] = {}
            check_data[date]['daily_net_profit'] = {'bch': 0.0, 'btc': 0.0, 'eos': 0.0, 'eth': 0.0, 'usdt': 0.0}
            check_data[date]['daily_fee'] = {'bch': 0.0, 'btc': 0.0, 'eos': 0.0, 'eth': 0.0, 'usdt': 0.0}
            for strategy_id, data in detail.items():
                net_prof = data['net_profit']
                check_data[date]['daily_net_profit'] = self.dict_add(data['net_profit'],
                                                                check_data[date]['daily_net_profit'])
                check_data[date]['daily_fee'] = self.dict_add(data['fee'], check_data[date]['daily_fee'])
                result = 0
                sym = ''
                # ethbtc
                if strategy_id.endswith("1"):
                    sym = 'ethbtc'
                    result = net_prof['btc'] + net_prof['eth'] * price['ethbtc'] + net_prof['usdt'] / price['btcusdt']
                # ethusdt
                elif strategy_id.endswith("2"):
                    sym = 'ethusdt'
                    result = net_prof['usdt'] + net_prof['eth'] * price['ethusdt']
                # btcusdt
                elif strategy_id.endswith("3"):
                    sym = 'btcusdt'
                    result = net_prof['usdt'] + net_prof['btc'] * price['btcusdt']
                # eoseth
                elif strategy_id.endswith("4"):
                    sym = 'eoseth'
                    result = net_prof['eth'] + net_prof['eos'] * price['eoseth']
                # ethbtc dualmakers
                elif strategy_id.endswith("5"):
                    sym = 'ethbtc'
                    result = net_prof['btc'] + net_prof['eth'] * price['ethbtc'] + net_prof['usdt'] / price['btcusdt']
                # bcheth
                elif strategy_id.endswith("6"):
                    sym = 'bcheth'
                    result = net_prof['eth'] + net_prof['bch'] * price['bcheth']
                # eosbtc
                elif strategy_id.endswith("7"):
                    sym = 'eosbtc'
                    result = net_prof['btc'] + net_prof['eos'] * price['eosbtc']
                # bchbtc
                elif strategy_id.endswith("8"):
                    sym = 'bchbtc'
                    result = net_prof['btc'] + net_prof['bch'] * price['bchbtc']
                else:
                    print("unknown str_id: %s" % strategy_id)
                if sym:
                    profit_data[date][sym][1] += result

        for data, details in profit_data.items():
            for sym, result in details.items():
                if sym:
                    total[sym] = 0.0

        for data, details in profit_data.items():
            for sym, result in details.items():
                if sym:
                    result[0] = True if result[1] >= 0 else False
                    total[sym] += result[1]
        pprint(self.d)
        pprint(profit_data)
        pprint(total)
        pprint(check_data)

        total_net_profit = {'bch': 0.0, 'btc': 0.0, 'eos': 0.0, 'eth': 0.0, 'usdt': 0.0}
        for date, daily_record in check_data.items():
            for sym, net_profit in daily_record['daily_net_profit'].items():
                total_net_profit[sym] += net_profit

        print(total_net_profit)



def get_huobi_price(metas):
    ret = {}
    for meta in metas:
        hb = HuobiRest(meta, None)
        trade_pair = hb.symbol
        price = hb.updateDepth()['bids'][0]['price']
        ret[trade_pair] = price
    return ret




if __name__ == "__main__":
    # price = {'ethbtc': 0.0777, 'ethusdt': 724, 'btcusdt': 9565,
    #          'eoseth':0.008260, 'eosbtc':0.00062677,
    #          'bcheth':1.53348, 'bchbtc':0.115750}
    #
    # parser = JsonParser('output.json')
    # parser.calc_with_price(price)
    metas = ['eth_btc', 'eth_usdt']
    print(get_huobi_price(metas))
