import datetime
import os
import time

import pymongo
import xlrd
import xlwt
from xlutils.copy import copy
from pymongo import MongoClient

from dquant.constants import Constants
from dquant.markets._binance_spot_rest import Binance
from dquant.common.mongo_conn import MongoConn

start = 1516180603000              # "2018-01-19 13:08:33"
end = 1516180603000                # "2018-01-17 17:16:43"


class BinanceTracer(Binance):
    def __init__(self, meta_code):
        super(BinanceTracer,self).__init__(meta_code=meta_code)
        self.db = MongoConn('localhost', 27017, username="Zzzz", password="123456").client.get_database('trade_binance')
        self.collection = self.db.get_collection(self.symbol.lower())
        self.l = 20000000
        self.timeout = 10
        print(self.symbol)
        # self.r = self.get_r()
        self.from_id = self.get_earliest_tid()-500
        print(self.from_id)
        # self.get_trades_loop()

    def get_earliest_tid(self):
        earliest_tid = self.collection.find(filter= {}, projection ={'tid': 1}).sort('timestamp', pymongo.ASCENDING)[0]['tid']
        return earliest_tid


    def parse_meta(self, meta_code):
        meta_table = {"eth_usdt": ("ETH", "USDT", "ETHUSDT"),
                      "btc_usdt": ("BTC", "USDT", "BTCUSDT"),
                      "eth_btc": ("ETH", "BTC", "ETHBTC"),}
        if meta_code in meta_table:
            ret = meta_table[meta_code]
        else:
            ret = ("ETH", "USDT", meta_code)
        return ret

    def get_trades_loop(self):
        '''
         _id       datetime obj
         tid       "id": 28457,
         price     "price": "4.00000100",
         amount    "qty": "12.00000000",
         timestamp  "time": 1499865549590,
         type      "isBuyerMaker": true,

         input:
             symbol
             limit: Default 500; max 500.
             fromId: TradeId to fetch from. Default gets most recent trades.

         死循环。每轮获取500个。每轮保存id的集合。找出max(id)。
         下一轮从max(id)开始找。
        '''
        fromId = self.from_id
        params = {'symbol': self.symbol, 'limit': 500}
        while True:
            try:
                if fromId:
                    params['fromId'] = fromId
                tids = []
                res = self.request(Constants.BINANCE_TRADES_REST, params=params, type='get')
                print(res)
                if not res or not isinstance(res, list):
                    time.sleep(3)
                    continue
                to_db = []
                for one in res:
                    the_id = one['id']
                    tids.append(the_id)

                    tmp = {
                        '_id': datetime.datetime.now(),
                        'tid': one['id'],
                        'price': one['price'],
                        'amount': one['qty'],
                        'isBuyerMaker': one['isBuyerMaker'],
                        'isBestMatch':one['isBestMatch'],
                        'timestamp': one['time'],
                        # 'type': True if one['isBuyerMaker'] else False,
                    }
                    to_db.append(tmp)
                    time.sleep(0.001)
                if to_db:
                    self.collection.insert(to_db)
                    fromId = min(tids) - 500

                if res[0]['time'] <= start:
                    break
                time.sleep(3)
            except Exception as e:
                print(e)
                continue

    def get_r(self):
        while True:
            try:
                params = {'symbol': self.symbol, 'limit': 500}
                tids = []
                res = self.request(Constants.BINANCE_TRADES_REST, params=params, type='get')
                print(res)
                if not isinstance(res, list):
                    time.sleep(5)
                    continue
                one = res[-1]
                the_id = one['id']
                tids.append(the_id)
                tmp = {
                    '_id': datetime.datetime.now(),
                    'tid': one['id'],
                    'price': one['price'],
                    'amount': one['qty'],
                    'isBuyerMaker': one['isBuyerMaker'],
                    'isBestMatch': one['isBestMatch'],
                    'timestamp': one['time'],
                    # 'type': True if one['isBuyerMaker'] else False,
                }
                time.sleep(5)
                return tmp['tid']
            except Exception as ex:
                print(ex)


    def get_trades(self):
        '''
         _id       datetime obj
         tid       "id": 28457,
         price     "price": "4.00000100",
         amount    "qty": "12.00000000",
         timestamp  "time": 1499865549590,
         type      "isBuyerMaker": true,

         input:
             symbol
             limit: Default 500; max 500.
             fromId: TradeId to fetch from. Default gets most recent trades.

         死循环。每轮获取500个。每轮保存id的集合。找出max(id)。
         下一轮从max(id)开始找。
        '''
        while True:
            params = {'symbol': self.symbol, 'limit': 500}
            try:
                print("l: %s; r: %s" % (self.l, self.r))
                this_id = self.l + self.r // 2
                params['fromId'] = this_id
                tids = []
                res = self.request(Constants.BINANCE_TRADES_REST, params=params, type='get')
                print(res)
                if not res or not isinstance(res, list):
                    time.sleep(5)
                    continue
                one = res[0]

                the_id = one['id']
                tids.append(the_id)
                tmp = {
                    '_id': datetime.datetime.now(),
                    'tid': one['id'],
                    'price': one['price'],
                    'amount': one['qty'],
                    'isBuyerMaker': one['isBuyerMaker'],
                    'isBestMatch':one['isBestMatch'],
                    'timestamp': one['time'],
                    # 'type': True if one['isBuyerMaker'] else False,
                }
                if start*0.9 <= tmp['tid'] <= start:
                    return tmp['tid']
                if tmp['tid'] < start:
                    self.l = this_id
                else:
                    self.r = this_id
                time.sleep(5)
                return self.get_trades()

            except Exception as e:
                print(e)

def find_trade():
    data = xlrd.open_workbook('交易记录1.xls')
    table = data.sheets()[0]
    ex = copy(data)
    wb = ex.get_sheet(0)
    nrows = table.nrows
    for i in range(nrows): # 循环逐行打印
        if i == 0: # 跳过第一行
            continue
        maker_data = table.row_values(i)[9]
        if maker_data:
            continue
        trade_time = table.row_values(i)[0]
        timeArray = time.strptime(trade_time, "%Y-%m-%d %H:%M:%S")
        timestamp_min = int(time.mktime(timeArray)*1000)
        timestamp_max = int(timestamp_min + 2000)
        symbol = table.row_values(i)[1]
        price = table.row_values(i)[3]
        if '.' in str(price):
            price_str = str(price).split('.')[0] +"."+ str(price).split('.')[-1][::-1].zfill(8)[::-1]
        else:
            price_str = str(price) + "." + 8*'0'
        amount = table.row_values(i)[4]
        if '.' in str(amount):
            amount_str = str(amount).split('.')[0] +"."+ str(amount).split('.')[-1][::-1].zfill(8)[::-1]
        else:
            amount_str = str(amount) + "." + 8*'0'
        side = table.row_values(i)[2]
        print(trade_time,price_str,amount_str)
        db = MongoConn('localhost', 27017, username="Zzzz", password="123456").client.get_database('trade_binance')
        collection = db.get_collection(symbol.lower())
        result = list(collection.find({"price":price_str, "amount": amount_str, "timestamp":{"$gt": timestamp_min, "$lt": timestamp_max}}))
        result_count = len(result)
        if result_count > 1:
            isbuyermaker = result[0]["isBuyerMaker"]
            for x in range(1, result_count):
                if result[x]["isBuyerMaker"] is not isbuyermaker:
                    wb.write(x, 9, result_count)
                    break

            # table.put_cell(i, 9, 2, result_count, 0)
            if side == '买' and isbuyermaker:
                maker = True
            if side == '买' and not isbuyermaker:
                maker = False
            if side == '卖' and not isbuyermaker:
                maker = True
            if side == '卖' and isbuyermaker:
                maker = False
            ctype = 4
            print(maker, isbuyermaker, int(result[0]["timestamp"]), int(result[0]["timestamp"])- timestamp_min)
            # table.put_cell(i, 9, ctype, maker, 0)
            # table.put_cell(i, 10, ctype, isbuyermaker, 0)
            # table.put_cell(i, 11, 2, int(result[0]["timestamp"]), 0)
            # table.put_cell(i, 12, 2, int(result[0]["timestamp"]) - timestamp_min, 0)
            wb.write(i, 9, maker)
            wb.write(i, 10, isbuyermaker)
            wb.write(i, 11, int(result[0]["timestamp"]))
            wb.write(i, 12, int(result[0]["timestamp"]) - timestamp_min)

        elif result_count == 1:

            isbuyermaker = result[0]["isBuyerMaker"]
            if side == '买' and isbuyermaker:
                maker = True
            if side == '买' and not isbuyermaker:
                maker = False
            if side == '卖' and not isbuyermaker:
                maker = True
            if side == '卖' and isbuyermaker:
                maker = False
            ctype = 4
            print(maker, isbuyermaker, int(result[0]["timestamp"]), int(result[0]["timestamp"])- timestamp_min)
            # table.put_cell(i, 9, ctype, maker, 0)
            # table.put_cell(i, 10, ctype, isbuyermaker, 0)
            # table.put_cell(i, 11, 2, int(result[0]["timestamp"]), 0)
            # table.put_cell(i, 12, 2, int(result[0]["timestamp"]) - timestamp_min, 0)
            wb.write(i, 9, maker)
            wb.write(i, 10, isbuyermaker)
            wb.write(i, 11, int(result[0]["timestamp"]))
            wb.write(i, 12, int(result[0]["timestamp"]) - timestamp_min)
            ex.save("交易记录1.xls")


def get_data():


    os.environ[Constants.DQUANT_ENV] = "dev"
    #find_trade()
    problem = []
    #done = ['VENETH', 'LTCUSDT', 'VENBTC', 'LTCBNB', 'BNBUSDT', 'BCCETH', 'LTCBTC', 'BCCUSDT', 'BCCBNB', 'ETHBTC','BNBBTC', 'BCCBTC','LTCETH', 'BNBETH', 'VENBNB']
    done = ['BNBBTC', 'BTCUSDT', 'BNBUSDT', 'LTCETH', 'LTCBNB', 'BCCUSDT', 'ETHUSDT', 'BCCBNB', 'BCCBTC', 'VENBNB', 'BNBETH', 'VENETH', 'ETHBTC', 'BCCETH', 'LTCBTC', 'LTCUSDT']
    problem = ['BTCUSDT', 'ETHUSDT', ]
    for symbol in problem:
        bi = BinanceTracer(symbol)
        bi.start()
        bi.get_trades_loop()
        bi.join()


if __name__ == "__main__":

    get_data()
