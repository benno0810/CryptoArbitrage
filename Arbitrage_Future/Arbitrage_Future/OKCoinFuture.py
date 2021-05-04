import hashlib
import hmac
import time
import json
import requests
import sys
import urllib
requests.adapters.DEFAULT_RETRIES = 5
delay_time = 0.1
class OKCoinFuture:
    def __init__(self,config,name="OKCoinFuture",account_name = "OKCoinFuture",currency="btc_usd",contract_type="quarter",lever_rate = 10):
        self.currency = currency
        self.access_key = config[name][account_name]["access_key"]
        self.secret_key = config[name][account_name]["secret_key"]
        # self.start_timeout = int(config[name]["start_time_out"])
        self.session = requests.Session()
        self.url = "https://www.okex.com"
        self.contract_type = contract_type
        self.lever_rate = str(lever_rate)
        self.rate = 6.71

    def get_account(self,tillOK = True,currency = None):
        while True:
            try:
                USERINFO_RESOURCE = "/api/v1/future_userinfo.do"
                params ={}
                params['api_key'] = self.access_key
                params['sign'] = self.buildMySign(params)

                res =  self.httpPost(self.url,USERINFO_RESOURCE,params)
                if res and res.has_key('result') and res['result']:
                    if not currency:
                        return res
                    result = {}
                    # print res
                    for curr in currency:
                        if res["info"].has_key(curr.lower()):
                            result.update({curr:float(res["info"][curr.lower()]['account_rights'])})
                    return result
                self.error("get Account",res)
                if not tillOK:
                    return res
            except Exception, ex:
                self.error("login",ex)
                if not tillOK:
                    return None
                continue

    def get_position(self,tillOK = True):
        while True:
            try:
                FUTURE_POSITION = "/api/v1/future_position.do?"
                params = {
                    'api_key':self.access_key,
                    'symbol':self.currency,
                    'contract_type':self.contract_type
                }
                params['sign'] = self.buildMySign(params)
                res = self.httpPost(self.url,FUTURE_POSITION,params)
                if res and res.has_key("result")and res["result"]:
                    return res
                self.error("get Position",res)
                if not tillOK:
                    return res
            except Exception,ex:
                self.error("get position",ex)
                if not tillOK:
                    return None
                continue
    def exchange_rate(self):
        while True:
            try:
                EXCHANGE_RATE = "/api/v1/exchange_rate.do"
                res = self.httpGet(self.url,EXCHANGE_RATE,'')
                # print res
                if res and res.has_key("rate"):
                    self.rate = float(res["rate"])
                    return res["rate"]
            except Exception, ex:
                self.error("exchange rate",ex)
                continue
    def getDepth(self,size=20,type="",tillOK=True):
        while True:
            try:
                DEPTH_RESOURCE = "/api/v1/future_depth.do"
                params=''
                symbol = self.currency
                # if symbol:
                params = 'symbol=%(symbol)s&size=%(size)d&contract_type=%(contract_type)s' %{'symbol':symbol,'size':size,"contract_type":self.contract_type}
                res =  self.httpGet(self.url,DEPTH_RESOURCE,params)
                if res and res.has_key('bids'):
                    return res
                self.error("getDepth",res)
                if not tillOK:
                    return res
            except Exception, ex:
                self.error("getDepth",ex)
                if not tillOK:
                    return None

    def future_trade(self,price='',amount='',tradeType='',matchPrice=''):
        FUTURE_TRADE = "/api/v1/future_trade.do?"
        params = {
            'api_key':self.access_key,
            'symbol':self.currency,
            'contract_type':self.contract_type,
            'amount':str(amount),
            'type':str(tradeType),
            'match_price':str(matchPrice),
            'lever_rate':self.lever_rate
        }
        if price:
            params['price'] = str(price)
        print params
        params['sign'] = self.buildMySign(params)
        return self.httpPost(self.url,FUTURE_TRADE,params)
    def long(self,amount,price=-1):
        try:
            if price<0:
                res = self.future_trade(amount = amount,tradeType = 1,matchPrice=1)
            else:
                res = self.future_trade(price=price,amount=amount,tradeType=1,matchPrice=0)

            if res and res.has_key("result") and res["result"]:
                return res
            else:
                self.error("long",res)
                return None
        except Exception, ex:
            self.error("long",ex)
            return None
    def close_long(self,amount,price=-1):
        try:
            if price<0:
                res =  self.future_trade(amount = amount,tradeType = 3,matchPrice=1)
            else:
                res = self.future_trade(price=price,amount=amount,tradeType=3,matchPrice=0)
            if res and res.has_key("result") and res["result"]:
                return res
            else:
                self.error("close long",res)
                return None
        except Exception, ex:
            self.error("close long",ex)
            return None
    def short(self,amount,price=-1):
        try:
            if price<0:
                res = self.future_trade(amount = amount,tradeType = 2,matchPrice=1)
            else:
                res = self.future_trade(price=price,amount=amount,tradeType=2,matchPrice=0)
            if res and res.has_key("result") and res["result"]:
                return res
            else:
                self.error("short",res)
                return None
        except Exception, ex:
            self.error("short",ex)
            return None
    def close_short(self,amount,price=-1):
        try:
            if price<0:
                res = self.future_trade(amount = amount,tradeType = 4,matchPrice=1)
            else:
                res = self.future_trade(price=price,amount=amount,tradeType=4,matchPrice=0)
            if res and res.has_key("result") and res["result"]:
                return res
            else:
                self.error("close short",res)
                return None
        except Exception, ex:
            self.error("close short",ex)
            return None
    def deleteOrder(self,orderId,tillOK = True):
        while True:
            try:
                FUTURE_CANCEL = "/api/v1/future_cancel.do?"
                params = {
                    'api_key':self.access_key,
                    'symbol':self.currency,
                    'contract_type':self.contract_type,
                    'order_id':orderId
                }
                params['sign'] = self.buildMySign(params)
                res =  self.httpPost(self.url,FUTURE_CANCEL,params)
                if res and res.has_key('result') and res['result']:
                    return res
                self.error("cancel Order",res)
                if not tillOK:
                    return res
            except Exception, ex:
                self.error("cancel Order",ex)
                if not tillOK:
                    return None
                continue

    def getOrder(self,orderId,tillOK=True):
        while True:
            try:
                FUTURE_ORDERINFO = "/api/v1/future_order_info.do?"
                params = {
                    'api_key':self.access_key,
                    'symbol':self.currency,
                    'contract_type':self.contract_type,
                    'order_id':orderId
                }
                params['sign'] = self.buildMySign(params)
                res =  self.httpPost(self.url,FUTURE_ORDERINFO,params)
                if res and res.has_key("result") and res["result"]:
                    return res
                self.error("get Order",res)
                if not tillOK:
                    return res
            except Exception, ex:
                self.error("get Order",ex)
                if not tillOK:
                    return None
                continue

    def error(self,func,err):
        time.sleep(delay_time)
        print >> sys.stderr, "OKCoin Future:\t",func," error,", err

    def buildMySign(self,params):
        sign = ''
        for key in sorted(params.keys()):
            sign += key + '=' + str(params[key]) +'&'
        data = sign+'secret_key='+self.secret_key
        return  hashlib.md5(data.encode("utf8")).hexdigest().upper()

    def httpGet(self,url,resource,params=''):
        # conn = http.client.HTTPSConnection(url, timeout=10)
        if params=='':
            response = self.session.get(url = url+resource)
        else:
            response = self.session.get(url=url+resource + '?' + params)

        # response = conn.getresponse()
        # print response.text
        data = response.text.decode('utf-8')
        return json.loads(data)

    def httpPost(self,url,resource,params):
         headers = {
                "Content-type" : "application/x-www-form-urlencoded",
         }
        # headers = {
        #     "Content-type": "application/x-www-form-urlencoded",
        # }
        # if add_to_headers:
        #     headers.update(add_to_headers)
        # postdata = urllib.urlencode(params)
        # # print postdata
        # # print url+"?"+postdata
        # response = self.session.get(url+"?"+postdata, headers=headers, timeout=5)
        # if response.status_code == 200:
        #     return response.json()

         temp_params = urllib.urlencode(params)
         res = self.session.post(url = url+resource,data = temp_params,headers = headers)
         # conn = http.client.HTTPSConnection(url, timeout=10)
         # conn.request("POST", resource, temp_params, headers)
         # response = conn.getresponse()
         data = res.text.decode('utf-8')
         params.clear()
         # conn.close()
         return json.loads(data)
import Platform
class OKCoinFuturePlatform(Platform.FuturePlatform):
    def __init__(self,config,name):
        super(OKCoinFuturePlatform,self).__init__(config,name,OKCoinFuture)
    def currency_pair2str(self,currency_pair):
        return currency_pair[0].lower()+'_'+currency_pair[1].lower()
    def tradePipeline(self,input_que,output_que,depth_input_queue,depth_output_queue,obj,currency_pair):
        while True:
            type,amount,price,price_limit = input_que.get()
            money = 0
            remain = amount
            while True:
                if amount < 0.01:
                    output_que.put((amount, money))
                    input_que.task_done()
                    break
                if type=="long":
                    if price_limit<0:
                        order = obj.long(amount=amount)
                    else:
                        order = obj.long(amount=amount, price=price)
                elif type == "close_long":
                    if price_limit<0:
                        order = obj.close_long(amount = amount)
                    else:
                        order = obj.close_long(amount=amount,price = price)
                elif type=="short":
                    if price_limit<0:
                        order = obj.short(amount=amount)
                    else:
                        order = obj.short(amount=amount, price=price)
                elif type == "close_short":
                    if price_limit<0:
                        order = obj.close_short(amount = amount)
                    else:
                        order = obj.close_short(amount=amount,price = price)
                if order == None:
                    time.sleep(1)
                    continue
                id = order["order_id"]
                wait_times = 3
                while wait_times > 0:
                    wait_times -= 1
                    time.sleep(1)

                    order = obj.getOrder(id)
                    print "okc", order
                    if order["orders"][0]["status"] == 2:
                        break
                if order["orders"][0]["status"] == 2:
                    if type=="short" or type=="close_long":
                        print "okcoin remain %s %f" % (type,0.0)
                        money += amount * 100.0
                        output_que.put((0.0, money))
                        input_que.task_done()
                        break
                    else:
                        print "okcoin remain %s 0.0"%(type)
                        money -= amount * 100.0
                        output_que.put((0.0, money))
                        input_que.task_done()
                        break
                else:
                    order = obj.deleteOrder(id)
                    while True:
                        order = obj.getOrder(id)
                        if order["orders"][0]["status"] == 2 or order["orders"][0]["status"] == -1:
                            break
                        else:
                            time.sleep(delay_time)
                    if type=="short" or type=="close_long":
                        money += float(order["orders"][0]["deal_amount"]) * 100.0
                        remain = float(order["orders"][0]["amount"]) - float(order["orders"][0]["deal_amount"])
                        print "okcoin remain %s %f" % (type,remain)
                    else:
                        money -= float(order["orders"][0]["deal_amount"]) * 100.0
                        remain = float(order["orders"][0]["amount"]) - float(order["orders"][0]["deal_amount"])
                        print "okcoin remain %s %f" % (type,remain)
                    if remain <= 0:
                        output_que.put((0.0, money))
                        input_que.task_done()
                        break
                print "get_price"
                depth_input_queue.put(remain)
                buy_price,sell_price = depth_output_queue.get()
                depth_output_queue.task_done()
                if type == "short" or type == "close_long":
                    price_now = sell_price
                    print "price_now okc", price_now
                    if price_limit>0 and price_now<price_limit:
                        output_que.put((remain,money))
                        input_que.task_done()
                        break
                else:
                    price_now = buy_price
                    print "price_now okc", price_now
                    if price_limit>0 and price_now>price_limit:
                        output_que.put((remain,money))
                        input_que.task_done()
                        break
                price = price_now
                amount = remain

if __name__ == "__main__":
    config = json.load(open("config_future.json",'r'))
    okcp = OKCoinFuturePlatform(config,"OKCoinFuture")
    print okcp.accounts["OKCoinFuture"]["objs"][0]["obj"].get_position()
    okcp.updateDepth({"BTC":1})
    okcp.updateBalance()
