import hashlib
import hmac
import time
import json
import requests
import sys
import Platform
api_address = r"https://yunbi.com/swagger/#/default"
requests.adapters.DEFAULT_RETRIES = 5
delay_time = 0.1
class YunBi:

    def __init__(self,config,name="YunBi",account_name = "YunBi",currency="ethcny"):
        self.currency = currency
        self.access_key = config[name][account_name]["access_key"]
        self.secret_key = config[name][account_name]["secret_key"]
        self.start_timeout = int(config[name][account_name]["start_time_out"])
        self.session = requests.Session()
    def get_account(self,tillOK = True,currency = None):
        while True:
            try:
                ###################
                ##query is all parameter except access_key and tonce
                ###################
                query = ""
                uri ="/api/v2/members/me.json"
                res = self.session.get(self.genUrl("GET",uri,{}))
                self.account = json.loads(res.text)
                # print self.account
                if self.account.has_key('error'):
                    self.error("login",res.text)
                    if tillOK:
                        continue
                    return None
                if not currency:
                    return self.account
                result = {}

                for acc in self.account["accounts"]:
                    for curr in currency:
                        if acc["currency"] == curr.lower():
                            result[curr] = float(acc["balance"])
                return result
            except Exception, ex:
                self.error("login",ex)
                if tillOK:
                    continue
                return None
    def getMarket(self):
        res = self.session.get("https://yunbi.com//api/v2/tikers/%s.json"%(self.currency))
        print res.text
    def getOrder(self,id,tillOK=True):
        while True:
            try:
                uri = "/api/v2/order.json"
                ###################
                ##query is all parameter except access_key and tonce
                ###################
                params = {}
                params["id"] = id
                res = self.session.get(self.genUrl("GET", uri, params),timeout=self.start_timeout)
                #print res.text
                js = json.loads(res.text)
                if js.has_key('error'):
                    self.error("getOrder",res.text)
                    if tillOK:
                        continue
                    return None
                return js
            except Exception, ex:
                self.error("getOrder",ex)
                if tillOK:
                    continue
                return None
    def deleteOrder(self,id,tillOK=True):
        while True:
            try:
                uri = "/api/v2/order/delete.json"
                ###################
                ##query is all parameter except access_key and tonce
                ###################
                params = {}
                params["id"] = id
                res = self.session.post(self.genUrl("POST", uri, params),timeout=self.start_timeout)
                #print res.text
                js = json.loads(res.text)
                if js.has_key('error'):
                    self.error("deleteOrder",res.text)
                    if tillOK:
                        continue
                    return None
                return js
            except Exception, ex:
                self.error("deleteOrder",ex)
                if tillOK:
                    continue
                return None
    def getK(self,period = -1,start_time = -1,number = 300):
        try:
            uri = "/api/v2/k.json"
            ###################
            ##query is all parameter except access_key and tonce
            ###################
            ##################################################
            ###############return buy,sell,low,high,last,vol

            params = {}
            if period>0:
                params["period"] = str(period)
            if start_time>0:
                params["time_stamp"]=str(start_time)
            if number>0:
                params["limit"] = str(number)
            params["market"] = self.currency
            res = self.session.get(self.genUrl("GET", uri, params))
            #print res.text
            js = json.loads(res.text)
            return js
        except Exception, ex:
            self.error("getK",ex)

    def getOrders(self):
        uri = "/api/v2/orders.json"
        ###################
        ##query is all parameter except access_key and tonce
        ###################
        params = {}
        params["market"] = self.currency
        # print self.genUrl("GET",uri,params)
        res = self.session.get(self.genUrl("GET", uri, params),timeout=self.start_timeout)
        print res.text
    def buy(self,volume,price):
        try:
            uri = "/api/v2/orders.json"
            ###################
            ##query is all parameter except access_key and tonce
            ###################
            params = {}
            params["market"] = self.currency
            params["volume"] = str(volume)
            params["price"] = str(price)
            params["side"] = "buy"
            res = self.session.post(self.genUrl("POST",uri,params),timeout=self.start_timeout+5)
            js = json.loads(res.text)
            if js and not js.has_key("error"):
                return js
            else:
                self.error("buy",js)
                return None
        except Exception, ex:
            self.error("buy",ex)
            return None
    def sell(self,volume,price):
        try:
            uri = "/api/v2/orders.json"
            ###################
            ##query is all parameter except access_key and tonce
            ###################
            params = {}
            params["market"] = self.currency
            params["volume"] = str(volume)
            params["price"] = str(price)
            params["side"] = "sell"
            res = self.session.post(self.genUrl("POST",uri,params),timeout=self.start_timeout+5)
            js = json.loads(res.text)
            if js and not js.has_key("error"):
                return js
            else:
                self.error("sell",js)
                return None
        except Exception, ex:
            self.error("sell",ex)
            return None
    def getDepth(self,tillOK=True):
        while True:
            try:
                res = self.session.get("https://yunbi.com//api/v2/depth.json?market=%s"%(self.currency),timeout=self.start_timeout+2)
                res_json = json.loads(res.text)
                if res_json.has_key('error'):
                    self.error("getDepth",res.text)
                    if not tillOK:
                        return None
                    continue
                # print res_json
                res_json["asks"].reverse()
                return res_json
            except Exception, ex:
                self.error("getDepth",ex)
                if not tillOK:
                    return None
                continue
    def error(self,func,err):
        time.sleep(delay_time)
        print >> sys.stderr, "YunBi:\t",func," error,", err

    def getTonce(self):
        return str(int(round(time.time()*1000)))
    def genUrl(self,type,uri,params={}):
        tonce = self.getTonce()
        params.update({"access_key":self.access_key,"tonce":tonce})
        keys = params.keys()
        keys.sort()
        query = ""
        for key in keys:
            query = "%s&%s=%s"%(query,key,params[key]) if len(query)!=0 else "%s=%s"%(key,params[key])
        signature = self.genSig(uri,query,type)
        # print "genUrl:\t","https://yunbi.com/%s?%s&signature=%s"%(uri,query,signature)
        return "https://yunbi.com/%s?%s&signature=%s"%(uri,query,signature)
    def genSig(self,uri,query,type):
        message = bytes("|".join([type,uri,query])).encode('utf-8')
        #print message
        secret = bytes(self.secret_key).encode('utf-8')
        signature = hmac.new(secret,message, digestmod=hashlib.sha256).hexdigest()
        # print "message:\t%s\ngenerate signature:\t %s"%(message,signature)
        return signature

class YunBiPlatform(Platform.Platform):
    def __init__(self,config,name):
        super(YunBiPlatform,self).__init__(config,name,YunBi)
        # print self.config
    def currency_pair2str(self,currency_pair):
        return currency_pair[0].lower()+currency_pair[1].lower()

    def tradePipeline(self,input_que,output_que,depth_input_queue,depth_output_queue,obj,currency_pair):
        while True:
            type, amount, price, price_limit = input_que.get()
            money = 0
            remain = amount
            sell = False if type == "buy" else True
            if amount == 0:
                output_que.put((0.0, 0.0))
                input_que.task_done()
                continue
            while True:
                order = None
                if sell:
                    order = obj.sell(volume=amount, price=price)
                else:
                    order = obj.buy(volume=amount, price=price)
                if order == None:
                    time.sleep(1)
                    continue
                id = order["id"]
                wait_times = 3
                while wait_times > 0:
                    wait_times -= 1
                    time.sleep(1)
                    order = obj.getOrder(id)
                    print "yb", order
                    if order["state"] == "done":
                        break
                if order["state"] == "done":
                    if sell:
                        print "yunbi remain sell %f" % 0.0
                        money += amount * (price)
                        output_que.put((0.0, money))
                        input_que.task_done()
                        break
                    else:
                        print "yunbi remain buy 0.0"
                        money -= amount * (price)
                        output_que.put((0.0, money))
                        input_que.task_done()
                        break
                else:
                    order = obj.deleteOrder(id)
                    while True:
                        order = obj.getOrder(id)
                        if order["state"] != "wait":
                            break
                        else:
                            time.sleep(delay_time)
                    # todo judge whether has been deleted
                    if sell:
                        money += float(order["executed_volume"]) * (price)
                        remain = float(order["remaining_volume"])
                        print "yunbi remain sell %f" % float(order["remaining_volume"])
                    else:
                        money -= float(order["executed_volume"]) * (price)
                        remain = float(order["remaining_volume"])
                        print "yunbi remain buy %f" % float(order["remaining_volume"])
                    if remain <= 0:
                        output_que.put((0.0, money))
                        input_que.task_done()
                        break
                print "get_price"
                depth_input_queue.put(remain)
                buy_price,sell_price = depth_output_queue.get()
                depth_output_queue.task_done()
                if sell:
                    price_now = sell_price
                    print "price_now yb", price_now
                    if price_limit>0 and price_now<price_limit:
                        output_que.put((remain,money))
                        input_que.task_done()
                        break
                else:
                    price_now = buy_price
                    print "price_now yb", price_now
                    if price_limit>0 and price_now>price_limit:
                        output_que.put((remain,money))
                        input_que.task_done()
                        break
                price = price_now
                amount = remain
            input.task_done()
if __name__ == "__main__":
    config = json.load(open("config_future.json",'r'))
    ybp = YunBiPlatform(config,"YunBi")
    ybp.updateDepth({"BTC":1})
    ybp.updateBalance()