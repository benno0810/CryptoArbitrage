import hashlib
import hmac
import time
import json
import requests
import sys
import urllib
import Platform
requests.adapters.DEFAULT_RETRIES = 5
delay_time = 0.1


class OKCoin:
    def __init__(self,config,name="OKCoin",account_name = "OKCoin",currency="eth_cny"):
        self.currency = currency
        self.access_key = config[name][account_name]["access_key"]
        self.secret_key = config[name][account_name]["secret_key"]
        # self.start_timeout = int(config[name]["start_time_out"])
        self.session = requests.Session()
        self.url = "https://www.okcoin.cn"

    def get_account(self,tillOK = True,currency = None):
        while True:
            try:
                USERINFO_RESOURCE = "/api/v1/userinfo.do"
                params ={}
                params['api_key'] = self.access_key
                params['sign'] = self.buildMySign(params)
                res = self.httpPost(self.url,USERINFO_RESOURCE,params)
                if res and res.has_key("result") and res["result"]:
                    if not currency:
                        return res
                    result = {}
                    for curr in currency:
                        if res["info"]["funds"]["free"].has_key(curr.lower()):
                            result.update({curr:float(res["info"]["funds"]["free"][curr.lower()])})
                    return result
                    # return res["info"]["funds"]["free"]
                self.error("login",res)
                if not tillOK:
                    return res
            except Exception, ex:
                self.error("login",ex)
                if not tillOK:
                    return None
                continue
    def getDepth(self,size=20,tillOK=True):
        while True:
            try:
                DEPTH_RESOURCE = "/api/v1/depth.do"
                params=''
                symbol = self.currency
                # if symbol:
                params = 'symbol=%(symbol)s&size=%(size)d' %{'symbol':symbol,'size':size}
                res = self.httpGet(self.url,DEPTH_RESOURCE,params)
                if res and res.has_key("bids"):
                    res["asks"].reverse()
                    return res
                self.error("getDepth",res)
                if not tillOK:
                    return res
            except Exception, ex:
                self.error("getDepth",ex)
                if not tillOK:
                    return None
                continue
    def buy(self,price,amount=-1):
        try:
            TRADE_RESOURCE = "/api/v1/trade.do"
            params = {
                'api_key':self.access_key,
                'symbol':self.currency,
            }

            if amount>0:
                params["type"] = "buy"
                params['amount'] = amount
            else:
                params["type"] = "buy_market"
            params['price'] = price

            params['sign'] = self.buildMySign(params)
            res =  self.httpPost(self.url,TRADE_RESOURCE,params)
            if res and res.has_key("result") and res["result"]:
                return res
            else:
                self.error("buy",res)
                return None
        except Exception, ex:
            self.error("buy",ex)
            return None

    def sell(self,amount,price=-1):
        try:
            TRADE_RESOURCE = "/api/v1/trade.do"
            params = {
                'api_key':self.access_key,
                'symbol':self.currency,
            }

            if price>0:
                params["type"] = "sell"
                params['price'] = price
            else:
                params["type"] = "sell_market"
            params['amount'] = amount
            params['sign'] = self.buildMySign(params)
            res = self.httpPost(self.url,TRADE_RESOURCE,params)
            if res and res.has_key("result") and res["result"]:
                return res
            else:
                self.error("buy",res)
                return None

        except Exception, ex:
            self.error("sell",ex)
            return None
    def deleteOrder(self,orderId,tillOK=True):
        while True:
            try:
                CANCEL_ORDER_RESOURCE = "/api/v1/cancel_order.do"
                params = {
                     'api_key':self.access_key,
                     'symbol':self.currency,
                     'order_id':orderId
                }
                params['sign'] = self.buildMySign(params)
                res =  self.httpPost(self.url,CANCEL_ORDER_RESOURCE,params)
                if res and res.has_key("result") and res["result"]:
                    return res
                if res and res.has_key("error_code") and res["error_code"] == 10050:
                    return res
                self.error("cancel order",res)
                if not tillOK:
                    return res

            except Exception, ex:
                self.error("cancel Order",ex)
                if not tillOK:
                    return None
                continue

    def getOrder(self,orderId,tillOK = True):
        while True:
            try:
                ORDER_INFO_RESOURCE = "/api/v1/order_info.do"
                params = {
                     'api_key':self.access_key,
                     'symbol':self.currency,
                     'order_id':orderId
                }
                params['sign'] = self.buildMySign(params)
                res = self.httpPost(self.url,ORDER_INFO_RESOURCE,params)
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
        print >> sys.stderr, "OKCoin:\t",func," error,", err

    def buildMySign(self,params):
        sign = ''
        for key in sorted(params.keys()):
            sign += key + '=' + str(params[key]) +'&'
        data = sign+'secret_key='+self.secret_key
        return  hashlib.md5(data.encode("utf8")).hexdigest().upper()

    def httpGet(self,url,resource,params=''):
        # conn = http.client.HTTPSConnection(url, timeout=10)
        response = self.session.get(url=url+resource + '?' + params)
        # response = conn.getresponse()
        data = response.text.decode('utf-8')
        return json.loads(data)

    def httpPost(self,url,resource,params):
         headers = {
                "Content-type" : "application/x-www-form-urlencoded",
         }
         temp_params = urllib.urlencode(params)
         res = self.session.post(url = url+resource,data = temp_params,headers = headers)
         data = res.text.decode('utf-8')
         params.clear()
         return json.loads(data)


class OKCoinPlatform(Platform.Platform):
    def __init__(self,config,name):
        super(OKCoinPlatform,self).__init__(config,name,OKCoin)
        # print self.config
    def currency_pair2str(self,currency_pair):
        return currency_pair[0].lower()+'_'+currency_pair[1].lower()

    def tradePipeline(self,input_que,output_que,depth_input_queue,depth_output_queue,obj,currency_pair):
        while True:
            type,amount,price,price_limit = input_que.get()
            money = 0
            remain = amount
            sell = False if type == "buy" else True
            while True:
                if amount < 0.01:
                    output_que.put((amount, money))
                    input_que.task_done()
                    break
                if sell:
                    if price_limit>=0:
                        order = obj.sell(amount=amount, price=price)
                    else:
                        order = obj.sell(amount=amount)
                else:
                    if price_limit>=0:
                        order = obj.buy(amount=amount, price=price)
                    else:
                        order = obj.buy(price = price*amount)
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
                    if sell:
                        print "okcoin remain sell %f" % 0.0
                        money += amount * price
                        output_que.put((0.0, money))
                        input_que.task_done()
                        break
                    else:
                        print "okcoin remain buy 0.0"
                        money -= amount * (price)
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
                    if sell:
                        money += float(order["orders"][0]["deal_amount"]) * (price)
                        remain = float(order["orders"][0]["amount"]) - float(order["orders"][0]["deal_amount"])
                        print "okcoin remain sell %f" % remain
                    else:
                        money -= float(order["orders"][0]["deal_amount"]) * (price)
                        remain = float(order["orders"][0]["amount"]) - float(order["orders"][0]["deal_amount"])
                        print "okcoin remain buy %f" % remain
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
    okcp = OKCoinPlatform(config,"OKCoin")
    okcp.updateDepth({"BTC":1})
    okcp.updateBalance()
