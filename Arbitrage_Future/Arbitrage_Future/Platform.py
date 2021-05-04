# coding=utf-8
import json
import Queue
import threading
from collections import defaultdict
class Platform(object):
    def __init__(self,config,name,obj):
        self.config = config
        self.name = name
        self.platform_config = config[name]
        self.depth_data_config = config["DepthData"]
        self.currency_pair = {}
        self.trade_accounts = {}
        self.accounts = {}
        for account_name,account_data in self.platform_config.items():
            if not account_data["valid"]:
                continue
            self.trade_accounts[account_name] = {}
            self.accounts[account_name] = {
                "objs":[],
                "currencies":set(),
                "balances":defaultdict(lambda:0),
                "account_input_queue":Queue.Queue(),
                "account_output_queue":Queue.Queue()
            }
            for currency_pair in account_data["currency_pairs"]:
                c_p = tuple(currency_pair)
                if not self.currency_pair.has_key(c_p):
                    self.currency_pair[c_p] = {
                        "objs":[],
                        "depth_input_queue":Queue.Queue(),
                        "depth_output_queue":Queue.Queue(),
                        "buy_price":None,
                        "sell_price":None
                    }
                trade_account_obj = {
                        "obj": obj(config,name = name,account_name = account_name,currency= self.currency_pair2str(c_p)),
                        "currency_pair": c_p,
                        "valid": True,
                        "trade_account_input_queue":Queue.Queue(),
                        "trade_account_output_queue":Queue.Queue(),
                        "depth_input_queue":self.currency_pair[c_p]["depth_input_queue"],
                        "depth_output_queue":self.currency_pair[c_p]["depth_output_queue"]
                    }
                trade_account_obj["trade_thread"] = threading.Thread(
                    target=self.tradePipeline,
                    args=(trade_account_obj["trade_account_input_queue"],
                          trade_account_obj["trade_account_output_queue"],
                          trade_account_obj["depth_input_queue"],
                          trade_account_obj["depth_output_queue"],
                          trade_account_obj["obj"],
                          c_p))
                trade_account_obj["trade_thread"].setDaemon(True)
                trade_account_obj["trade_thread"].start()
                self.currency_pair[c_p]["objs"].append(trade_account_obj)
                self.trade_accounts[account_name][c_p] = trade_account_obj
                self.accounts[account_name]["objs"].append(trade_account_obj)
                self.accounts[account_name]["currencies"].add(c_p[0])
                self.accounts[account_name]["currencies"].add(c_p[1])
        # print self.currency_pair
        # print self.accounts
        # print self.trade_accounts
        #建立depth的thread
        for c_p,obj in self.currency_pair.items():
            # print c_p,obj
            obj["depth_thread"] = threading.Thread(target=self.getDepthPipeline,args=(obj["depth_input_queue"],
                                                                                      obj["depth_output_queue"],
                                                                                      obj["objs"][0]["obj"],
                                                                                      float(self.depth_data_config[c_p[0]]["TradeAdvanceRatio"]),
                                                                                      float(self.depth_data_config[c_p[0]]["OffsetCoin"]),
                                                                                      int(self.depth_data_config[c_p[0]]["OffsetPlayer"],)))
            obj["depth_thread"].setDaemon(True)
            obj["depth_thread"].start()
        #建立accounts的thread
        for c_p,obj in self.accounts.items():
            # print c_p,obj
            obj["accounts_thread"] = threading.Thread(target=self.getAccountPipeline,args=(obj["account_input_queue"],
                                                                                      obj["account_output_queue"],
                                                                                      obj["objs"][0]["obj"],
                                                                                      obj["currencies"],))
            obj["accounts_thread"].setDaemon(True)
            obj["accounts_thread"].start()
    def tradePipeline(self,input_que,output_que,depth_input_queue,depth_output_queue,obj,currency_pair):
        raise NotImplementedError()
    #amount是一个dict，比如：{"BTC":1}表示对于所有交易BTC的账户，计算depth
    def updateDepthPut(self,amount):
        for c_p,obj in self.currency_pair.items():
            if amount.has_key(c_p[0]):
                obj["depth_input_queue"].put(amount[c_p[0]])
    def updateDepthGet(self,amount):
        for c_p,obj in self.currency_pair.items():
            if amount.has_key(c_p[0]):
                obj["buy_price"], obj["sell_price"] = obj["depth_output_queue"].get()
                for account in obj["objs"]:
                    account["sell_price"] = obj["sell_price"]
                    account["buy_price"] = obj["buy_price"]
                obj["depth_output_queue"].task_done()
            print "%s : %s : sell : %f buy : %f"%(self.name,self.currency_pair2str(c_p),obj["sell_price"],obj["buy_price"])

    def getAccountPipeline(self,input_que,output_que,obj,currencies):
        while True:
            input_que.get()
            res = obj.get_account(tillOK=True,currency=currencies)
            output_que.put(res)
            input_que.task_done()

    def updateBalancePut(self):
        for account_name,obj in self.accounts.items():
            # print account_name,self.accounts[account_name]
            # print account_name
            self.accounts[account_name]["account_input_queue"].put(None)

    def updateBalanceGet(self):
        total_balance = defaultdict(lambda:0)
        for account_name,obj in self.accounts.items():
            self.accounts[account_name]["balances"] = self.accounts[account_name]["account_output_queue"].get()
            print "Balance : %s : %s"%(account_name,json.dumps(self.accounts[account_name]["balances"]))
            for cur,bal in self.accounts[account_name]["balances"].items():
                total_balance[cur]+=bal
            self.accounts[account_name]["account_output_queue"].task_done()
        # self.accounts["total_balance"] = total_balance
        print "Total Balance : %s"%json.dumps(total_balance),"\n"
    def updateBalance(self):
        self.updateBalancePut()
        self.updateBalanceGet()

    def updateDepth(self,amount):
        self.updateDepthPut(amount)
        self.updateDepthGet(amount)

    def getDepthPipeline(self,input_que,output_que,obj,trade_advance_ratio,offset_coin,offset_player):
        while True:
            nCoin = input_que.get()
            res = obj.getDepth(tillOK = True)
            # print res
            sell_price = self.thresCoin(nCoin*trade_advance_ratio,offset_coin=offset_coin,offset_player = offset_player,list=res["bids"])
            buy_price = self.thresCoin(nCoin*trade_advance_ratio,offset_coin=offset_coin,offset_player = offset_player,list = res["asks"])
            output_que.put((buy_price[1],sell_price[1]))
            input_que.task_done()

    def currency_pair2str(self,currency_pair):
        raise NotImplementedError()

    def thresCoin(self,thres, offset_coin, offset_player, list):
        acc = 0
        for i in range(offset_player, len(list)):
            acc += float(list[i][1])
            if acc > thres + offset_coin:
                return (thres, float(list[i][0]), list)
        return (acc, float(list[-1][0]), list)

class FuturePlatform(Platform):
    def __init__(self,config,name,obj):
        super(FuturePlatform,self).__init__(config,name,obj)
