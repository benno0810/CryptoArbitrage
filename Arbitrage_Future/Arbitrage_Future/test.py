# !/usr/local/bin/python
# -*- coding:utf-8 -*-
import YunBi
import CNBTC
import json
import threading
import Queue
import time
import logging
import numpy
import message
import random
open_platform = [True,True,True,True]
numpy.set_printoptions(suppress=True)
# logging.basicConfig(level=logging.DEBUG,
#                 format="[%(asctime)20s] [%(levelname)8s] %(filename)10s:%(lineno)-5s --- %(message)s",
#                 datefmt="%Y-%m-%d %H:%M:%S",
#                 filename="log/%s.log"%time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())),
#                 filemode='w')
# console = logging.StreamHandler()
# console.setLevel(logging.INFO)
# formatter = logging.Formatter("[%(asctime)20s] [%(levelname)8s] %(filename)10s:%(lineno)-5s --- %(message)s", "%Y-%m-%d %H:%M:%S")
# console.setFormatter(formatter)
# logging.getLogger('').addHandler(console)
coin_status = [-1,-1,-1,-1]
money_status = [-1,-1,-1,-1]
history = open("log/historyPrice_%s.txt"%time.strftime('%Y_%m_%d_%H_%M_%S', time.localtime(time.time())),"a")
# output = open("journalist.txt",'a')
balance = open("log/balance%s.txt"%time.strftime('%Y_%m_%d %H_%M_%S', time.localtime(time.time())),'a')
ybQue1 = Queue.Queue()
ybQue2 = Queue.Queue()
hbQue1 = Queue.Queue()
hbQue2 = Queue.Queue()
okcQue1 = Queue.Queue()
okcQue2 = Queue.Queue()
cnbtcQue1 = Queue.Queue()
cnbtcQue2 = Queue.Queue()
ybTradeQue1 = Queue.Queue()
ybTradeQue2 = Queue.Queue()
cnbtcTradeQue1 = Queue.Queue()
cnbtcTradeQue2 = Queue.Queue()
hbTradeQue1 = Queue.Queue()
hbTradeQue2 = Queue.Queue()
okcTradeQue1 = Queue.Queue()
okcTradeQue2 = Queue.Queue()
ybAccountQue1 = Queue.Queue()
ybAccountQue2 = Queue.Queue()
cnbtcAccountQue1 = Queue.Queue()
cnbtcAccountQue2 = Queue.Queue()
hbAccountQue1 = Queue.Queue()
hbAccountQue2 = Queue.Queue()
okcAccountQue1 = Queue.Queue()
okcAccountQue2 = Queue.Queue()
alertQue = Queue.Queue()

total_trade_coin = 0
delay_time = 0.2
config = json.load(open("config.json","r"))
#####max coin # in each trade
maxTradeLimitation = float(config["MaxCoinTradeLimitation"])
tel_list = config["tel"]
# maxTradeLimitation_yb_buy_cnbtc_sell = float(config["MaxCoinTradeLimitation_yb_buy_cnbtc_sell"])
# maxTradeLimitation_yb_buy_hb_sell = float(config["MaxCoinTradeLimitation_yb_buy_hb_sell"])
# maxTradeLimitation_yb_sell_hb_buy = float(config["MaxCoinTradeLimitation_yb_sell_hb_buy"])
# maxTradeLimitation_hb_buy_cnbtc_sell = float(config["MaxCoinTradeLimitation_hb_buy_cnbtc_sell"])
# maxTradeLimitation_hb_sell_cnbtc_buy = float(config["MaxCoinTradeLimitation_hb_sell_cnbtc_buy"])
#####max coin # for each account
maxCoin = float(config["MaxCoinLimitation"])
#####if spread over this threshold, we trade
max_thres_limitation = float(config["max_thres_limitation"])
spread_threshold_yb_sell_cnbtc_buy = float(config["spread_threshold_yb_sell_cnbtc_buy"])
spread_threshold_yb_buy_cnbtc_sell = float(config["spread_threshold_yb_buy_cnbtc_sell"])
spread_threshold_yb_buy_hb_sell = float(config["spread_threshold_yb_buy_hb_sell"])
spread_threshold_yb_sell_hb_buy = float(config["spread_threshold_yb_sell_hb_buy"])
spread_threshold_hb_buy_cnbtc_sell = float(config["spread_threshold_hb_buy_cnbtc_sell"])
spread_threshold_hb_sell_cnbtc_buy = float(config["spread_threshold_hb_sell_cnbtc_buy"])
random_range = float(config["RandomRange"])


spread_threshold_yb_sell_okc_buy = float(config["spread_threshold_yb_sell_okc_buy"])
spread_threshold_yb_buy_okc_sell = float(config["spread_threshold_yb_buy_okc_sell"])
spread_threshold_okc_buy_hb_sell = float(config["spread_threshold_okc_buy_hb_sell"])
spread_threshold_okc_sell_hb_buy = float(config["spread_threshold_okc_sell_hb_buy"])
spread_threshold_okc_buy_cnbtc_sell = float(config["spread_threshold_okc_buy_cnbtc_sell"])
spread_threshold_okc_sell_cnbtc_buy = float(config["spread_threshold_okc_sell_cnbtc_buy"])
max_diff_thres = float(config["max_diff_thres"])
#######if coin # is lower than alert thres, it will increase the thres
alert_thres_coin = float(config["alert_thres_coin"])
alert_thres_money = float(config["alert_thres_money"])
thres_coin = float(config["thres_coin"])
thres_money = float(config["thres_money"])
#######max thres increase is slop*alert_thres
slope = float(config["alert_slope"])
# print max_diff_thres,alert_thres,slope
# spread_threshold = float(config["spread_threshold"])
# spread_threshold_minor = float(config["spread_threshold_minor"])
#####if we start a trade, we will accept all trade until spread reach lowest spread threshold, after that, we cancel all trade
lowest_spread_threshold = float(config["lowest_spread_threshold"])
trade_multiplier_ratio = float(config["TradeMultiplyRatio"])
# lowest_spread_threshold_minor = float(config["lowest_spread_threshold_minor"])
#####the trade price is max trade limitation*trade ratio behind the min/max price of ask/bid
trade_ratio = float(config["TradeAdvanceRatio"])
# trade_ratio_minor = float(config["TradeAdvanceRatio_minor"])
#####slippage
slippage = float(config["slippage"])
tmpThres = maxTradeLimitation*trade_ratio
# tmpThres_minor = maxTradeLimitation_minor*trade_ratio
offset_player = int(config["offset_player"])
# offset_player_minor = int(config["offset_player_minor"])
offset_coin = float(config["offset_coin"])
# offset_coin_minor = float(config["offset_coin_minor"])
########return 0 accumulate amount
########return 1 price
########return 2 list
def cnbtcThresCoin(thres,offset_coin,offset_player,list):
    acc = 0
    for i in range(offset_player,len(list)):
        acc += list[i][1]
        if acc > thres+offset_coin:
            return (thres,list[i][0],list)
    return (acc,list[-1][0],list)
def ybThresCoin(thres,offset_coin,offset_player,list):
    acc = 0
    for i in range(offset_player,len(list)):
        acc += float(list[i][1])
        if acc > thres+offset_coin:
            return (thres,float(list[i][0]),list)
    return (acc,float(list[-1][0]),list)
def hbThresCoin(thres,offset_coin,offset_player,list):
    acc = 0
    for i in range(offset_player,len(list)):
        acc += float(list[i][1])
        if acc > thres+offset_coin:
            return (thres,float(list[i][0]),list)
    return (acc,float(list[-1][0]),list)

def okcThresCoin(thres,offset_coin,offset_player,list):
    acc = 0
    for i in range(offset_player,len(list)):
        acc += list[i][1]
        if acc > thres+offset_coin:
            return (thres,list[i][0],list)
    return (acc,list[-1][0],list)


def ybRun():
    while True:
        yb = ybQue1.get()
        if yb == None:
            ybQue1.task_done()
            break
        else:
            while True:
                depth = yb.getDepth()
                if depth:
                    break
            depth["asks"].reverse()
            ybQue2.put((ybThresCoin(tmpThres,offset_coin,offset_player,depth["bids"]),depth["timestamp"]))
            ybQue2.put((ybThresCoin(tmpThres,offset_coin,offset_player,depth["asks"]),depth["timestamp"]))
        ybQue1.task_done()
def okcRun():
    while True:
        okc = okcQue1.get()
        if okc == None:
            okcQue1.task_done()
            break
        else:
            while True:
                depth = okc.getDepth()
                if depth:
                    break
            depth["asks"].reverse()
            okcQue2.put((okcThresCoin(tmpThres,offset_coin,offset_player,depth["bids"]),"-99999999"))
            okcQue2.put((okcThresCoin(tmpThres,offset_coin,offset_player,depth["asks"]),"-99999999"))
        okcQue1.task_done()
def hbRun():
    while True:
        hb = hbQue1.get()
        if hb == None:
            hbQue1.task_done()
            break
        else:
            while True:
                depth = hb.getDepth()
                if depth and depth["status"] == "ok":
                    break
            # depth["tick"]["asks"].reverse()
            hbQue2.put((hbThresCoin(tmpThres,offset_coin,offset_player,depth["tick"]["bids"]),depth["ts"]/1000))
            hbQue2.put((hbThresCoin(tmpThres,offset_coin,offset_player,depth["tick"]["asks"]),depth["ts"]/1000))
        hbQue1.task_done()
def cnbtcRun():
    while True:
        cnbtc = cnbtcQue1.get()
        if cnbtc == None:
            cnbtcQue1.task_done()
            break
        else:
            while True:
                depth = cnbtc.getDepth()
                if depth:
                    break
            depth["asks"].reverse()
            cnbtcQue2.put((cnbtcThresCoin(tmpThres,offset_coin,offset_player,depth["bids"]),depth["timestamp"]))
            cnbtcQue2.put((cnbtcThresCoin(tmpThres,offset_coin,offset_player,depth["asks"]),depth["timestamp"]))
        cnbtcQue1.task_done()
#######tradeque1[0]:obj
#######tradeque1[1]:buy or sell
#######tradeque1[2]:amount
#######tradeque1[3]:price
#######tradeque1[4]:limit_price
def ybTradeRun():
    while True:
        yb_tuple = ybTradeQue1.get()
        money = 0
        if yb_tuple == None:
            ybTradeQue1.task_done()
            break
        yb = yb_tuple[0]
        amount = yb_tuple[2]
        remain = amount
        price = yb_tuple[3]
        if amount==0:
            ybTradeQue2.put((0.0,0.0))
            ybTradeQue1.task_done()
            continue
        sell = True
        if yb_tuple[1] == "buy":
            sell = False
        times = 10
        while True:
            order = None
            if sell:
                order = yb.sell(volume = amount,price=price-slippage)
            else:
                order = yb.buy(volume = amount, price = price + slippage)
            if order!= None:
                if order.has_key("error"):
                    time.sleep(delay_time)
                    print "yb",order
                    continue
                id = order["id"]
                wait_times = 3
                while wait_times>0:
                    wait_times-=1
                    time.sleep(1)
                    while True:
                        order = yb.getOrder(id)
                        if order!=None:
                            if order.has_key("error"):
                                time.sleep(delay_time)
                                print "yb",order
                                continue
                            break
                    print "yb",order
                    if order["state"] == "done":
                        break
                if order["state"] == "done":
                    if sell:
                        print "yunbi remain sell %f"%0.0
                        money+=amount*(price-slippage)
                        ybTradeQue2.put((0.0,money))
                        break
                    else:
                        print "yunbi remain buy 0.0"
                        money-=amount*(price+slippage)
                        ybTradeQue2.put((0.0,money))
                        break
                else:
                    # order["state"] == "wait":
                    while True:
                        order = yb.deleteOrder(id)
                        print "yb",order
                        if order!=None:
                            if order.has_key("error"):
                                print "yb,delete",order
                                time.sleep(delay_time)
                                continue
                            break
                    while True:
                        order = yb.getOrder(id)
                        print "yb",order

                        if order!=None:
                            if order.has_key("error"):
                                time.sleep(delay_time)
                                print "yb",order
                                continue
                            if order["state"] != "wait":
                                break
                            else:
                                time.sleep(delay_time)
                                # break
                    #todo judge whether has been deleted
                    if sell:
                        money+=float(order["executed_volume"])*(price-slippage)
                        remain = float(order["remaining_volume"])
                        print "yunbi remain sell %f"%float(order["remaining_volume"])
                    else:
                        money-=float(order["executed_volume"])*(price+slippage)
                        remain = float(order["remaining_volume"])
                        print "yunbi remain buy %f"%float(order["remaining_volume"])
                    if remain <=0:
                        ybTradeQue2.put((0.0,money))
                        break
            print "get_price"
            while True:
                depth = yb.getDepth()
                if depth:
                    depth["asks"].reverse()
                    break
            if sell:
                price_now = ybThresCoin(remain*trade_ratio,offset_coin,offset_player,depth["bids"])[1]
                print "price_now yb",price_now,yb_tuple[4]
                if price_now<yb_tuple[4]:
                    ybTradeQue2.put((remain,money))
                    break
            else:
                price_now = ybThresCoin(remain*trade_ratio,offset_coin,offset_player,depth["asks"])[1]
                print "price_now yb",price_now
                if price_now>yb_tuple[4]:
                    ybTradeQue2.put((remain,money))
                    break
            price = price_now
            amount = remain
            times-=1
        ybTradeQue1.task_done()
def okcTradeRun():
    while True:
        okc_tuple = okcTradeQue1.get()
        money = 0
        if okc_tuple == None:
            okcTradeQue1.task_done()
            break
        okc = okc_tuple[0]
        amount = okc_tuple[2]
        remain = amount
        price = okc_tuple[3]
        if amount==0:
            okcTradeQue2.put((0.0,0.0))
            okcTradeQue1.task_done()
            continue
        sell = True
        if okc_tuple[1] == "buy":
            sell = False
        times = 10
        while True:
            order = None
            if sell:
                order = okc.sell(volume = amount,price=price-slippage)
            else:
                order = okc.buy(volume = amount, price = price+slippage)
            if order!= None:
                if order["result"] != True:
                    print "okc",order
                    time.sleep(delay_time)
                    continue
                id = order["order_id"]
                wait_times = 3
                while wait_times>0:
                    wait_times-=1
                    time.sleep(1)
                    while True:
                        order = okc.getOrder(id)
                        if order!=None:
                            if order["result"] != True:
                                time.sleep(delay_time)
                                print "okc",order
                                continue
                            break
                    print "okc",order
                    if order["orders"][0]["status"] == 2:
                        break
                if order["orders"][0]["status"] == 2:
                    if sell:
                        print "okcoin remain sell %f"%0.0
                        money+=amount*(price-slippage)
                        okcTradeQue2.put((0.0,money))
                        break
                    else:
                        print "okcoin remain buy 0.0"
                        money-=amount*(price+slippage)
                        okcTradeQue2.put((0.0,money))
                        break
                else:
                    # order["state"] == "wait":
                    while True:
                        order = okc.deleteOrder(id)
                        if order!=None:
                            if order["result"] != True:
                                time.sleep(delay_time)
                                print "okc",order
                                if order["error_code"]==10050:
                                    break
                                continue
                            break
                    while True:
                        order = okc.getOrder(id)
                        if order!=None:
                            if order["result"] != True:
                                time.sleep(delay_time)
                                print "okc",order
                                continue
                            if order["orders"][0]["status"] == 2 or order["orders"][0]["status"]== -1:
                                break
                            else:
                                time.sleep(delay_time)
                    #todo judge whether has been deleted
                    if sell:
                        money+=float(order["orders"][0]["deal_amount"])*(price-slippage)
                        remain = float(order["orders"][0]["amount"]) - float(order["orders"][0]["deal_amount"])
                        print "okcoin remain sell %f"%remain
                    else:
                        money-=float(order["orders"][0]["deal_amount"])*(price+slippage)
                        remain = float(order["orders"][0]["amount"])-float(order["orders"][0]["deal_amount"])
                        print "okcoin remain buy %f"%remain
                    if remain<=0:
                        okcTradeQue2.put((0.0,money))
                        break


            print "get_price"
            while True:
                depth = okc.getDepth()
                if depth:
                    depth["asks"].reverse()
                    break
            if sell:
                price_now = okcThresCoin(remain*trade_ratio,offset_coin,offset_player,depth["bids"])[1]
                print "price_now okc",price_now,okc_tuple[4]
                if price_now<okc_tuple[4]:
                    okcTradeQue2.put((remain,money))
                    break
            else:
                price_now = okcThresCoin(remain*trade_ratio,offset_coin,offset_player,depth["asks"])[1]
                print "price_now okc",price_now
                if price_now>okc_tuple[4]:
                    okcTradeQue2.put((remain,money))
                    break
            price = price_now
            amount = remain
            times-=1
        okcTradeQue1.task_done()
def hbTradeRun():
    while True:
        hb_tuple = hbTradeQue1.get()
        money = 0
        if hb_tuple == None:
            hbTradeQue1.task_done()
            break
        hb = hb_tuple[0]
        amount = hb_tuple[2]
        remain = amount
        price = hb_tuple[3]
        if amount==0:
            hbTradeQue2.put((0.0,0.0))
            hbTradeQue1.task_done()
            continue
        sell = True
        if hb_tuple[1] == "buy":
            sell = False
        times = 10
        while True:
            order = None
            if sell:
                order = hb.sell(volume = amount,price=price-slippage)
                #todo
                if order!=None and order["status"] == "ok":
                    order = hb.place_order(order["data"])
            else:
                #todo
                order = hb.buy(volume = amount, price = price + slippage)
                if order!=None and order["status"] == "ok":
                    order = hb.place_order(order["data"])
            if order!= None:
                if order["status"]!="ok":
                    print "hb",order
                    time.sleep(delay_time)
                    continue
                id = order["data"]
                wait_times = 3
                while wait_times>0:
                    wait_times-=1
                    time.sleep(1)
                    while True:
                        order = hb.getOrder(id)
                        if order!=None:
                            if order["status"]!="ok":
                                time.sleep(delay_time)
                                print "hb",order
                                continue
                            break
                    print "hb",order
                    if order["data"]["state"] == "filled":
                        break
                #todo
                if order["data"]["state"] == "filled":
                    if sell:
                        print "huobi remain sell %f"%0.0
                        money+=amount*(price-slippage)
                        hbTradeQue2.put((0.0,money))
                        break
                    else:
                        print "huobi remain buy 0.0"
                        money-=amount*(price+slippage)
                        hbTradeQue2.put((0.0,money))
                        break
                else:
                    # order["state"] == "wait":
                    while True:
                        print id
                        order = hb.deleteOrder(id)
                        if order!=None:
                            if order["status"]!="ok":
                                if order['status'] == 'error' and order['err-code'] == 'order-orderstate-error':
                                    break
                                print "hb",order
                                continue
                            break
                    while True:
                        order = hb.getOrder(id)
                        if order!=None:
                            if order["status"]!="ok":
                                time.sleep(delay_time)
                                print "hb",order
                                continue
                            print "hb",order
                            if order["data"]["state"] == "canceled" or order["data"]["state"] == "filled" or  order["data"]["state"] == "partial-canceled" or order["data"]["state"] == "partial-filled":
                                break
                            else:
                                time.sleep(delay_time)
                    #todo judge whether has been deleted
                    if sell:
                        money+=float(order["data"]["field-amount"])*(price-slippage)
                        remain = float(order["data"]["amount"])-float(order["data"]["field-amount"])
                        print "huobi remain sell %f"%remain
                    else:
                        money-=float(order["data"]["field-amount"])*(price+slippage)
                        remain = float(order["data"]["amount"])-float(order["data"]["field-amount"])
                        print "huobi remain buy %f"%remain
                    if remain<=0:
                        hbTradeQue2.put((0.0,money))
                        break

            print "get_price"
            while True:
                depth = hb.getDepth()
                if depth:
                    break
            if sell:
                price_now = hbThresCoin(remain*trade_ratio,offset_coin,offset_player,depth['tick']["bids"])[1]
                print "price_now hb",price_now,hb_tuple[4]
                if price_now<hb_tuple[4]:
                    hbTradeQue2.put((remain,money))
                    break
            else:
                price_now = hbThresCoin(remain*trade_ratio,offset_coin,offset_player,depth['tick']["asks"])[1]
                print "price_now hb",price_now
                if price_now>hb_tuple[4]:
                    hbTradeQue2.put((remain,money))
                    break
            price = price_now
            amount = remain
            times-=1
        hbTradeQue1.task_done()

def cnbtcTradeRun():
    while True:
        cnbtc_tuple = cnbtcTradeQue1.get()
        if cnbtc_tuple == None:
            cnbtcTradeQue1.task_done()
            break
        # print cnbtc_tuple
        money = 0;
        cnbtc = cnbtc_tuple[0]
        amount = cnbtc_tuple[2]
        remain = amount
        price = cnbtc_tuple[3]
        if amount==0:
            cnbtcTradeQue2.put((0.0,0.0))
            cnbtcTradeQue1.task_done()
            continue
        buy = True
        if cnbtc_tuple[1] == "sell":
            buy = False
        times = 10
        while True:
            if buy:
                order = cnbtc.buy(volume = amount,price=price+slippage)
            else:
                order = cnbtc.sell(volume=amount,price=price-slippage)
            if order!= None:
                if order.has_key("code") and order["code"] != 1000:
                    time.sleep(delay_time)
                    print "cnbtc",order
                    continue
                id = order["id"]
                wait_times = 5
                while wait_times>0:
                    wait_times-=1
                    time.sleep(1)
                    while True:
                        order = cnbtc.getOrder(id)
                        if order!=None:
                            break
                    print "cnbtc",order
                    ####2 is done
                    ####
                    if order["status"] == 2:
                        break
                if order["status"] == 2:
                    if buy:
                        print "cnbtc remain buy ",0.0
                        money-=amount*(price+slippage)
                        cnbtcTradeQue2.put((0.0,money))
                    else:
                        print "cnbtc remain sell 0.0"
                        money+=amount*(price-slippage)
                        cnbtcTradeQue2.put((0.0,money))
                    break
                elif order["status"] == 0 or order["status"] == 3:
                    while True:
                        order = cnbtc.deleteOrder(id)
                        if order!=None:
                            if order.has_key("code") and order["code"] != 1000:
                                print json.dumps(order,ensure_ascii=False)
                                if order["code"] == 3001:
                                    break
                                time.sleep(delay_time)
                                continue
                            break
                    while True:
                        order = cnbtc.getOrder(id)
                        if order!=None:
                            # print order
                            if order.has_key("code") and order["code"] != 1000:
                                print "cnbtc",order
                                time.sleep(delay_time)
                                continue
                            #todo judge whether is deleted
                            if order["status"]==1 or order["status"] == 2:
                                break
                            else:
                                time.sleep(delay_time)
                    print "cnbtc",order
                    if buy:
                        money-=float(order["trade_amount"])*(price+slippage)
                        remain = float(order["total_amount"]) - float(order["trade_amount"])
                        print "cnbtc remain buy %f/%f"%(remain,float(order["total_amount"]))
                    else:
                        money+=float(order["trade_amount"])*(price-slippage)
                        remain = float(order["total_amount"]) - float(order["trade_amount"])
                        print "cnbtc remain sell %f/%f"%(remain,float(order["total_amount"]))
                    if remain<=0:
                        cnbtcTradeQue2.put((0.0,money))
                        break
                else:
                    if buy:
                        money-=float(order["trade_amount"])*(price+slippage)
                        remain = float(order["total_amount"]) - float(order["trade_amount"])
                        print "cnbtc remain buy %f/%f"%(remain,float(order["total_amount"]))
                    else:
                        money+=float(order["trade_amount"])*(price-slippage)
                        remain = float(order["total_amount"]) - float(order["trade_amount"])
                        print "cnbtc remain sell %f/%f"%(remain,float(order["total_amount"]))
                    if remain<=0:
                        cnbtcTradeQue2.put((0.0,money))
                        break
            print "get_depth"
            while True:
                depth = cnbtc.getDepth()
                depth["asks"].reverse()
                if depth:
                    break
            if buy:
                price_now = cnbtcThresCoin(remain*trade_ratio,offset_coin,offset_player,depth["asks"])[1]
                print "prince_now cnbtc",price_now
                if price_now>cnbtc_tuple[4]:
                    cnbtcTradeQue2.put((remain,money))
                    break
            else:
                price_now = cnbtcThresCoin(remain*trade_ratio,offset_coin,offset_player,depth["bids"])[1]
                print "prince_now cnbtc",price_now
                if price_now<cnbtc_tuple[4]:
                    cnbtcTradeQue2.put((remain,money))
                    break
            price = price_now
            amount = remain
            times-=1
        cnbtcTradeQue1.task_done()

def ybAccountRun():
    while True:
        yb = ybAccountQue1.get()
        yb_cny = 0
        yb_eth = 0
        while True:
            yb_acc = yb.get_account()
            if yb_acc!= None:
                if yb_acc.has_key("error"):
                    time.sleep(delay_time)
                    print yb_acc
                    continue
                break
        for acc in yb_acc["accounts"]:
            if acc["currency"] == "cny":
                yb_cny=float(acc["balance"])
            elif acc["currency"] == "eth":
                yb_eth= float(acc["balance"])

        ybAccountQue1.task_done()
        ybAccountQue2.put((yb_cny,yb_eth))

def cnbtcAccountRun():
    while True:
        cnbtc = cnbtcAccountQue1.get()
        cnbtc_cny = 0
        cnbtc_eth = 0
        while True:
            cnbtc_acc = cnbtc.get_account()
            if cnbtc_acc!= None:
                if cnbtc_acc.has_key("code") and cnbtc_acc["code"] != 1000:
                    time.sleep(delay_time)
                    print cnbtc_acc
                    continue
                break
        cnbtc_eth=cnbtc_acc["result"]["balance"]["ETH"]["amount"]
        cnbtc_cny+=cnbtc_acc["result"]["balance"]["CNY"]["amount"]

        cnbtcAccountQue1.task_done()
        cnbtcAccountQue2.put((cnbtc_cny,cnbtc_eth))

def okcAccountRun():
    while True:
        time.sleep(delay_time)
        okc = okcAccountQue1.get()
        okc_cny = 0
        okc_eth = 0
        while True:
            okc_acc = okc.get_account()
            if okc_acc!= None:
                if okc_acc["result"]!=True:
                    time.sleep(delay_time)
                    print "okc",okc_acc
                    continue
                break
        okc_eth = float(okc_acc["info"]["funds"]["free"]["eth"])
        okc_cny = float(okc_acc["info"]["funds"]["free"]["cny"])
        # print okc_acc

        okcAccountQue1.task_done()
        okcAccountQue2.put((okc_cny,okc_eth))

def hbAccountRun():
    while True:
        hb = hbAccountQue1.get()
        hb_cny = 0
        hb_eth = 0
        while True:
            hb_acc = hb.get_account()
            if hb_acc!= None:
                if hb_acc["status"]!="ok":
                    print hb_acc
                    continue
                break
        for mon in hb_acc["data"]["list"]:
            if mon["currency"]=="cny" and mon["type"] == "trade":
                hb_cny = float(mon["balance"])
            if mon["currency"] == "eth" and mon["type"] == "trade":
                hb_eth = float(mon["balance"])

        hbAccountQue1.task_done()
        hbAccountQue2.put((hb_cny,hb_eth))

import sys
import numpy.matlib
def setThreshold(cny_list,eth_list,brokerage_fee,cash_fee,thres_list_now,thres_list_origin,number,price,tick_coin,name_list):
    trade_multiplier = numpy.ones([number,number])
    thres_list = thres_list_origin.copy()
    sell_times = eth_list/tick_coin
    buy_times = cny_list/price/tick_coin
    trade_broker = numpy.add.outer(brokerage_fee,brokerage_fee)*price*1.1
    trade_cash = numpy.add.outer(cash_fee,numpy.zeros(cash_fee.shape[0]))*price*1.05
    length = cny_list.shape[0]
    print "buy_times",buy_times
    print "sell_times",sell_times
    tmp = buy_times.copy()
    tmp[tmp>thres_money] = thres_money
    tmp = (-tmp+thres_money)*slope
    tmp[tmp>max_thres_limitation] = max_thres_limitation
    offset = numpy.matlib.repmat(tmp,length,1)
    tmp = buy_times.copy()
    tmp[tmp>thres_money] = thres_money
    tmp = (-tmp+thres_money)*5/thres_money
    tmp[tmp>1] = 1
    max_diff_thres_tmp = max(0,max_diff_thres)
    tmp_mul = numpy.matlib.repmat(tmp.reshape(length,1),1,length)
    trade_multiplier+=tmp_mul*trade_multiplier_ratio

    tmp = numpy.matlib.repmat(tmp.reshape(length,1),1,length)
    # print 123
    offset_cash = -numpy.multiply(tmp,numpy.add.outer(cash_fee,numpy.zeros(cash_fee.shape[0]))*price*1.05)
    # print tmp

    # tmp = numpy.matlib.repmat(tmp.reshape(length,1),1,length)

    # print tmp
    tmp = sell_times.copy()
    tmp[tmp>thres_coin] = thres_coin
    tmp = (-tmp+thres_coin)*slope
    tmp[tmp>max_thres_limitation] = max_thres_limitation
    offset += numpy.matlib.repmat(tmp.reshape(length,1),1,length)

    tmp = sell_times.copy()
    tmp[tmp>thres_coin] = thres_coin
    tmp = (-tmp+thres_coin)*5/thres_coin
    tmp[tmp>1] = 1
    tmp_mul = numpy.matlib.repmat(tmp,length,1)
    trade_multiplier+=tmp_mul*trade_multiplier_ratio
    tmp = numpy.matlib.repmat(tmp,length,1)
    # print 123
    offset_cash -= numpy.multiply(tmp,numpy.add.outer(cash_fee,numpy.zeros(cash_fee.shape[0]))*price*1.05)
    # print offset
    # buy_times<100
    alertQue.put((buy_times,sell_times,number))
    # offset[offset<max_diff_thres_tmp] = max_diff_thres_tmp
    offset[offset>max_thres_limitation] = max_thres_limitation
    print offset
    # print offset
    # print trade_broker,trade_cash,offset_cash
    thres_list =  trade_broker+trade_cash+offset_cash+max_diff_thres_tmp+offset+thres_list_origin
    # print thres_list
    thres_list[:,buy_times<=8] = 999999
    thres_list[sell_times<=8,:] = 999999
    buy_tmp = (thres_money-buy_times.copy())*slope
    buy_tmp[buy_tmp<0] = 0
    buy_tmp[buy_tmp>max_diff_thres_tmp] = max_diff_thres_tmp
    buy_tmp_n_n = numpy.matlib.repmat(buy_tmp.reshape(length, 1), 1, length)


    sell_tmp = (thres_coin-sell_times.copy())*slope
    sell_tmp[sell_tmp<0] = 0
    sell_tmp[sell_tmp>max_diff_thres_tmp] = max_diff_thres_tmp


    sell_tmp_n_n = numpy.matlib.repmat(sell_tmp,length,1)
    tmp_n_n = numpy.maximum(sell_tmp_n_n,buy_tmp_n_n)
    # print thres_list
    # print tmp_n_n
    thres_list -= tmp_n_n
    # thres_list -= sell_tmp
    numpy.fill_diagonal(thres_list,999999)
    numpy.fill_diagonal(trade_multiplier,0)
    trade_multiplier[trade_multiplier>2] = 2
    # print trade_multiplier
    # print thres_list
    # thres_list = numpy.maximum.reduce([thres_list,(trade_broker+trade_cash)])
    # print buy_times<=1
    # print thres_list
    # result = thres_list_origin.copy()
    # result[:number,:number] = thres_list
    # thres_list[2,0] = 0
    # thres_list[2,1] = 0
    # thres_list[1,2] = 0
    # thres_list[0,2] = 0
    # print thres_list
    return thres_list,trade_multiplier
def alert():
    while True:
        alertTuple = alertQue.get()
        buy_times = alertTuple[0]
        sell_times = alertTuple[1]
        number = alertTuple[2]
        for i in range(number):
            if open_platform[i]:
                if buy_times[i] <= 8:
                    if money_status[i] == 0 or money_status[i] == 1:
                        for tel in tel_list:
                            res = message.send_sms("提醒：%s的账户完全没钱了" % name_list[i], tel)
                            print res
                    money_status[i] = 2
                    print >> sys.stderr, "%s has no money!!!!!!!!!!!!!!!!!!!!!" % name_list[i]
                elif buy_times[i] < alert_thres_money:
                    if money_status[i] == 0:
                        for tel in tel_list:
                            message.send_sms("提醒：%s快没钱了，只能买%f次了" % (name_list[i],buy_times[i]), tel)
                    money_status[i] = 1
                    print >> sys.stderr, "%s is low money!!!!!!!!!!!!!!!!!!!!!!" % name_list[i]
                else:
                    money_status[i] = 0
                if sell_times[i] <= 8:
                    if coin_status[i] == 0 or coin_status[i] == 1:
                        for tel in tel_list:
                            message.send_sms("提醒：%s的账户完全没币了" % name_list[i], tel)
                    coin_status[i] = 2
                    print >> sys.stderr, "%s has no coin!!!!!!!!!!!!!!!!!!!!!!" % name_list[i]
                elif sell_times[i] < alert_thres_coin:
                    if coin_status[i] == 0:
                        for tel in tel_list:
                            message.send_sms("提醒：%s快没币了，只能卖%f次了" % (name_list[i],sell_times[i]), tel)
                    coin_status[i] = 1
                    print >> sys.stderr, "%s is low coin!!!!!!!!!!!!!!!!!!!!!!" % name_list[i]
                else:
                    coin_status[i] = 0
        alertQue.task_done()

import HuoBi
import OKCoin
open_okc = open_platform[3]
open_yb = open_platform[1]
open_cnbtc = open_platform[0]
open_hb = open_platform[2]
if open_yb:
    yb = YunBi.Yunbi(config,"LiChen")
    print yb.get_account()
else:
    yb = None
# import gzip
# from StringIO import StringIO
#
# buf = StringIO(acc["name"])
# f = gzip.GzipFile(fileobj=buf)
# print f.read()
# sss = acc["name"].encode("raw_unicode_escape").decode()

# print ss
# logging.info("YB Account "+json.dumps(yb.get_account(),ensure_ascii=False))
if open_cnbtc:
    cnbtc = CNBTC.CNBTC(config)
    print("cnbtc Account "+str(cnbtc.get_account()))
else:
    cnbtc = None
if open_hb:
    hb = HuoBi.HuoBi(config)
    print("HB Account "+str(hb.get_account()))
else:
    hb = None
if open_okc:
    okc = OKCoin.OKCoin(config)
    print("OKCoin Account "+str(okc.get_account()))
    okc_thread = threading.Thread(target=okcRun)
    okc_thread.setDaemon(True)
    okc_thread.start()
else:
    okc = None
if open_yb:
    yb_thread = threading.Thread(target=ybRun)
    yb_thread.setDaemon(True)
    yb_thread.start()
if open_cnbtc:
    cnbtc_thread = threading.Thread(target=cnbtcRun)
    cnbtc_thread.setDaemon(True)
    cnbtc_thread.start()
if open_hb:
    hb_thread = threading.Thread(target=hbRun)
    hb_thread.setDaemon(True)
    hb_thread.start()
if open_okc:
    okc_trade_thread = threading.Thread(target=okcTradeRun)
    okc_trade_thread.setDaemon(True)
    okc_trade_thread.start()
if open_yb:
    yb_trade_thread = threading.Thread(target=ybTradeRun)
    yb_trade_thread.setDaemon(True)
    yb_trade_thread.start()
if open_cnbtc:
    cnbtc_trade_thread = threading.Thread(target = cnbtcTradeRun)
    cnbtc_trade_thread.setDaemon(True)
    cnbtc_trade_thread.start()
if open_hb:
    hb_trade_thread = threading.Thread(target=hbTradeRun)
    hb_trade_thread.setDaemon(True)
    hb_trade_thread.start()
if open_okc:
    okc_account_thread = threading.Thread(target=okcAccountRun)
    okc_account_thread.setDaemon(True)
    okc_account_thread.start()
if open_yb:
    yb_account_thread = threading.Thread(target=ybAccountRun)
    yb_account_thread.setDaemon(True)
    yb_account_thread.start()
if open_cnbtc:
    cnbtc_account_thread = threading.Thread(target = cnbtcAccountRun)
    cnbtc_account_thread.setDaemon(True)
    cnbtc_account_thread.start()
if open_hb:
    hb_account_thread = threading.Thread(target=hbAccountRun)
    hb_account_thread.setDaemon(True)
    hb_account_thread.start()

alertThread = threading.Thread(target=alert)
alertThread.setDaemon(True)
alertThread.start()
total_coin = 0
total_money = 0
tick = 0
last_total_eth = 0
last_total_cny = 0
first_total_eth = 0
first_total_cny = 0
first = True
platform_number = 4
name_list = ["CNBTC","YunBi","HuoBi","OKCoin"]
obj_list = [cnbtc,yb,hb,okc]
que1_list = [cnbtcQue1,ybQue1,hbQue1,okcQue1]
que2_list = [cnbtcQue2,ybQue2,hbQue2,okcQue2]
trade_que1_list = [cnbtcTradeQue1,ybTradeQue1,hbTradeQue1,okcTradeQue1]
trade_que2_list = [cnbtcTradeQue2,ybTradeQue2,hbTradeQue2,okcTradeQue2]
thres_list = numpy.array([[999999,spread_threshold_yb_buy_cnbtc_sell,spread_threshold_hb_buy_cnbtc_sell,spread_threshold_okc_buy_cnbtc_sell],
              [spread_threshold_yb_sell_cnbtc_buy,999999,spread_threshold_yb_sell_hb_buy,spread_threshold_yb_sell_okc_buy],
              [spread_threshold_hb_sell_cnbtc_buy,spread_threshold_yb_buy_hb_sell,9999999,spread_threshold_okc_buy_hb_sell],
              [spread_threshold_okc_sell_cnbtc_buy,spread_threshold_yb_buy_okc_sell,spread_threshold_okc_sell_hb_buy,999999]])
thres_list_origin = thres_list.copy()
has_ts = [True,True,True,False]
platform_list = []
for i in range(platform_number):
    platform_list.append(
        {
            "name":name_list[i],
            "obj":obj_list[i],
            "que1":que1_list[i],
            "que2":que2_list[i],
            "trade_que1":trade_que1_list[i],
            "trade_que2":trade_que2_list[i],
            "depth_buy":None,
            "depth_sell":None,
            "has_ts":has_ts[i]
        }
    )
brokerage_fee = numpy.asarray([0.0004,0.001,0.002,0.001])
cash_fee = numpy.asarray([0.001,0.001,0.002,0.002])

while True:
    print 'tick',tick
    for platform in platform_list:
        if platform["obj"]!=None:
            platform["que1"].put(platform["obj"])
    if open_yb:
        ybAccountQue1.put(yb)
    if open_okc:
        okcAccountQue1.put(okc)
    if open_cnbtc:
        cnbtcAccountQue1.put(cnbtc)
    if open_hb:
        hbAccountQue1.put(hb)
    for platform in platform_list:
        if platform["obj"]!=None:
            platform["depth_sell"] = platform["que2"].get()
            platform["depth_buy"] = platform["que2"].get()

    ###depth[0] is amount
    ###depth[1] is price
    ###depth[2] is list        platform_list["depth_buy"] = platform["que2"].get()

    max_diff = -1000
    trade_info = dict()
    average_price = 0
    open_num = 0
    for i in range(platform_number):
        if platform_list[i]["obj"]!=None:
            open_num+=1
            average_price+=platform_list[i]["depth_buy"][0][1]+platform_list[i]["depth_sell"][0][1]
    average_price /= open_num*2.0/1.01
    print 'average_price %f'%average_price
    brokerage_trade = numpy.add.outer(brokerage_fee,brokerage_fee)*average_price
    cash_trade = numpy.add.outer(cash_fee,numpy.zeros(cash_fee.shape[0]))*average_price

    tick+=1
    if tick % 1 == 0:
        total_cny = 0
        total_eth = 0
        yb_cny = 0
        yb_eth = 0
        cnbtc_cny = 0
        cnbtc_eth = 0
        hb_cny = 0
        hb_eth = 0
        okc_cny = 0
        okc_eth = 0
        if open_yb:
            yb_cny,yb_eth = ybAccountQue2.get()
            print "yb_balance:%f %f"%(yb_eth,yb_cny)
        if open_okc:
            okc_cny,okc_eth = okcAccountQue2.get()
            print "okc_balance:%f %f"%(okc_eth,okc_cny)
        if open_hb:
            hb_cny,hb_eth = hbAccountQue2.get()
            print "hb balance:%f %f"%(hb_eth,hb_cny)
        if open_cnbtc:
            cnbtc_cny,cnbtc_eth = cnbtcAccountQue2.get()
            print "cnbtc balance:%f %f"%(cnbtc_eth,cnbtc_cny)
        total_cny = yb_cny+hb_cny+cnbtc_cny+okc_cny
        total_eth = yb_eth+hb_eth+cnbtc_eth+okc_eth
        balance.write("%s %f %f %f %f %f %f %f %f %f %f\n"%(time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())),
                                                cnbtc_eth,cnbtc_cny,yb_eth,yb_cny,hb_eth,hb_cny,okc_eth,okc_cny,total_eth,total_cny))
        history.write("%s "%time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())))
        for i in range(platform_number):
            if platform_list[i]["obj"]!=None:
                history.write("%f %f "%(platform_list[i]["depth_buy"][0][1],platform_list[i]["depth_sell"][0][1]))
            else:
                history.write('0 0 ')
        history.write('\n')


        cny_list = numpy.asarray([cnbtc_cny,yb_cny,hb_cny,okc_cny])
        eth_list = numpy.asarray([cnbtc_eth,yb_eth,hb_eth,okc_eth])
        last_total_eth = total_eth
        last_total_cny = total_cny
        if first:
            first_total_cny = total_cny
            first_total_eth = total_eth
            first = False
        # history.write("%s %f %f %f %f %f %f\n" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),
        #                                           yb_depth[0][1], cnbtc_depth[0][1], yb_depth[0][1] - cnbtc_depth[0][1],
        #                                           yb_depth_minor[0][1], cnbtc_depth_minor[0][1],
        #                                           cnbtc_depth_minor[0][1] - yb_depth_minor[0][1]))
        balance.flush()
        history.flush()

        if tick%1 == 0:
            thres_list,trade_multiplier = setThreshold(cny_list,eth_list,brokerage_fee,cash_fee,thres_list,thres_list_origin,platform_number,average_price,maxTradeLimitation,name_list)
        # print thres_list
    i1 = None
    j1 = None
    for i in range(platform_number):
        for j in range(platform_number):
            if i!=j and platform_list[i]["obj"]!=None and platform_list[j]["obj"]!=None:
                # if platform_list[i]["has_ts"] and platform_list[j]["has_ts"]:
                #     print i,j,int(platform_list[i]["depth_sell"][1]),int(platform_list[j]["depth_buy"][1])
                #     if (int(platform_list[i]["depth_sell"][1])-int(platform_list[j]["depth_buy"][1]))>5:
                #         continue
                # print platform_list[i],platform_list[j]

                if platform_list[i]["depth_sell"][0][1] - platform_list[j]["depth_buy"][0][1]>thres_list[i,j] and platform_list[i]["depth_sell"][0][1] - platform_list[j]["depth_buy"][0][1]-thres_list[i,j]>max_diff:
                    max_diff = platform_list[i]["depth_sell"][0][1]-platform_list[j]["depth_buy"][0][1]-thres_list[i,j]
                    trade_info["sell_depth"] = platform_list[i]["depth_sell"]
                    trade_info["buy_depth"] = platform_list[j]["depth_buy"]
                    trade_info["sell_name"] = platform_list[i]["name"]
                    trade_info["buy_name"] = platform_list[j]["name"]
                    trade_info["sell_que1"] = platform_list[i]["trade_que1"]
                    trade_info["sell_que2"] = platform_list[i]["trade_que2"]
                    trade_info["buy_que1"] = platform_list[j]["trade_que1"]
                    trade_info["buy_que2"] = platform_list[j]["trade_que2"]
                    trade_info["sell_obj"] = platform_list[i]["obj"]
                    trade_info["buy_obj"]=platform_list[j]["obj"]
                    i1 = i
                    j1 = j
    if max_diff>0:
        print "max_diff %f"%max_diff
        buy_depth = trade_info["buy_depth"]
        sell_depth = trade_info["sell_depth"]
        # print("BuySide:%s  timestamp:%s  amount:\t%f price:\t%f"%(trade_info["buy_name"],buy_depth[1],buy_depth[0][0],buy_depth[0][1],str(buy_depth[0][2])))
        # print('SellSide:%s timestamp:%s  amount:\t%f price:\t%f'%(trade_info["sell_name"],sell_depth[1],sell_depth[0][0],sell_depth[0][1],str(sell_depth[0][2])))
        # print 'BuySide:%s  timestamp:%s  amount:\t%f price:\t%f asks:%s'%(trade_info["buy_name"],buy_depth[1],buy_depth[0][0],buy_depth[0][1],str(buy_depth[0][2]))
        # print 'SellSide:%s timestamp:%s  amount:\t%f price:\t%f bids:%s'%(trade_info["sell_name"],sell_depth[1],sell_depth[0][0],sell_depth[0][1],str(sell_depth[0][2]))
        amount = int(min(buy_depth[0][0],sell_depth[0][0])*1.0/trade_ratio*trade_multiplier[i1,j1]*100)/100.0
        amount +=int((random.random()-0.5)*2*(random_range+0.01)*100)/100.0
        if amount<0:
            amount = 0
        amount_buy=amount
        amount_sell=amount_buy
        limit = (buy_depth[0][1]+sell_depth[0][1])*1.0/2.0
        if total_coin>0.0001:
            amount_buy = max(amount_buy-total_coin,0)
        elif total_coin<-0.0001:
            amount_sell = max(amount_sell+total_coin,0)
        print "%s buy %f coins at %f and limit %f" %(trade_info["buy_name"],amount_buy,buy_depth[0][1],limit-lowest_spread_threshold/2.0)
        trade_info["buy_que1"].put((trade_info["buy_obj"],"buy",amount_buy,buy_depth[0][1],limit-lowest_spread_threshold/2.0))
        print "%s sell %f coins at %f and limit %f" %(trade_info["sell_name"],amount_sell,sell_depth[0][1],limit+lowest_spread_threshold/2.0)
        trade_info["sell_que1"].put((trade_info["sell_obj"],"sell",amount_sell,sell_depth[0][1],limit+lowest_spread_threshold/2.0))
        sell_remain = trade_info["sell_que2"].get()
        buy_remain = trade_info["buy_que2"].get()
        # output.write('%f, %f, %f, %f\n'%(sell_remain[0]-amount_sell,amount_buy-buy_remain[0],buy_remain[1],sell_remain[1]))
        # output.flush()
        total_coin+=sell_remain[0]-amount_sell-buy_remain[0]+amount_buy
        total_money+=sell_remain[1]+buy_remain[1]
        print "%s_remain:%f\t %s_remain:%f,total_remain:%f"%(trade_info["buy_name"],buy_remain[0],trade_info["sell_name"],sell_remain[0],maxCoin)
        print"coin:%f,money:%f"%(total_coin,total_money)
        maxCoin-=max(sell_remain[0],buy_remain[0])
        # if maxCoin<0:
        #     hbQue1.put(None)
        #     cnbtcQue1.put(None)
        #     hbTradeQue1.put(None)
        #     cnbtcTradeQue1.put(None)
        #     break
    else:
        # average_price = 0
        for i in range(platform_number):
            for j in range(platform_number):
                if i!=j and platform_list[i]["obj"]!=None and platform_list[j]["obj"]!=None:
                    print "no trade %s sell:%f %s buy:%f diff:%15f thres:%20f diff_brokerage:%20f"%(platform_list[i]["name"],platform_list[i]["depth_sell"][0][1],platform_list[j]["name"],platform_list[j]["depth_buy"][0][1],
                                                                   platform_list[i]["depth_sell"][0][1]-platform_list[j]["depth_buy"][0][1],thres_list[i,j],platform_list[i]["depth_sell"][0][1]-platform_list[j]["depth_buy"][0][1]-thres_list[i,j])
            # average_price+=platform_list[i]["depth_buy"][0][1]+platform_list[i]["depth_sell"][0][1]
        # average_price/=2.0*platform_number
        print average_price
        # print "no trade yb sell:%f cnbtc buy:%f diff:%f"%(yb_depth_sell[0][1],cnbtc_depth_buy[0][1],yb_depth_sell[0][1]-cnbtc_depth_buy[0][1])
        # print "no trade hb sell:%f cnbtc buy:%f diff:%f"%(hb_depth_sell[0][1],cnbtc_depth_buy[0][1],hb_depth_sell[0][1]-cnbtc_depth_buy[0][1])
        # print "no trade yb buy:%f cnbtc sell:%f diff:%f"%(yb_depth_buy[0][1],cnbtc_depth_sell[0][1],cnbtc_depth_sell[0][1]-yb_depth_buy[0][1])
        # print "no trade hb buy:%f cnbtc sell:%f diff:%f"%(hb_depth_buy[0][1],cnbtc_depth_sell[0][1],cnbtc_depth_sell[0][1]-hb_depth_buy[0][1])
        # print "no trade yb buy:%f hb sell:%f diff:%f"%(yb_depth_buy[0][1],hb_depth_sell[0][1],hb_depth_sell[0][1]-yb_depth_buy[0][1])
        # print "no trade hb buy:%f yb sell:%f diff:%f"%(hb_depth_buy[0][1],yb_depth_sell[0][1],yb_depth_sell[0][1]-hb_depth_buy[0][1])
    print "balance %f %f diff: %f %f %f first:%f %f"%(total_eth,total_cny, total_eth - last_total_eth,total_cny - last_total_cny,(total_eth - last_total_eth)*2000.0,
                                                           total_eth - first_total_eth,total_cny - first_total_cny)

    print '\n'

    #
    # if hb_depth_sell[0][1]-cnbtc_depth_buy[0][1]>spread_threshold_hb_sell_cnbtc_buy and abs(int(cnbtc_depth_buy[1])-int(hb_depth_sell[1])<=3) and hb_depth_sell[0][1]-cnbtc_depth_buy[0][1]>max_diff:
    #     if cnbtc_depth_sell[0][1]-hb_depth_buy[0][1]>spread_threshold_hb_buy_cnbtc_sell and abs(int(hb_depth_buy[1])-int(cnbtc_depth_sell[1])<=3) and cnbtc_depth_sell[0][1]-hb_depth_buy[0][1]>max_diff:
    #     max_diff = cnbtc_depth_sell[0][1]-hb_depth_buy[0][1]
    #     trade_info["sell_depth"] = cnbtc_depth_sell
    #     trade_info["buy_depth"] = hb_depth_buy
    #     trade_info["sell_name"] = "CNBTC"
    #     trade_info["buy_name"] = "HuoBi"
    #     trade_info["sell_que1"] = cnbtcTradeQue1
    #     trade_info["sell_que2"] = cnbtcTradeQue2
    #     trade_info["buy_que1"] = hbTradeQue1
    #     trade_info["buy_que2"] = hbTradeQue2
    #     trade_info["buy_obj"] = hb
    #     trade_info["sell_obj"]=cnbtc
    # if hb_depth_sell[0][1]-yb_depth_buy[0][1]>spread_threshold_yb_buy_hb_sell and abs(int(yb_depth_buy[1])-int(hb_depth_sell[1])<=3) and hb_depth_sell[0][1]-yb_depth_buy[0][1]>max_diff:
    #     max_diff = hb_depth_sell[0][1]-yb_depth_buy[0][1]
    #     trade_info["sell_depth"] = hb_depth_sell
    #     trade_info["buy_depth"] = yb_depth_buy
    #     trade_info["sell_name"] = "HuoBi"
    #     trade_info["buy_name"] = "YunBi"
    #     trade_info["sell_que1"] = hbTradeQue1
    #     trade_info["sell_que2"] = hbTradeQue2
    #     trade_info["buy_que1"] = ybTradeQue1
    #     trade_info["buy_que2"] = ybTradeQue2
    #     trade_info["sell_obj"] = hb
    #     trade_info["buy_obj"]=yb
    # if yb_depth_sell[0][1]-hb_depth_buy[0][1]>spread_threshold_yb_sell_hb_buy and abs(int(hb_depth_buy[1])-int(yb_depth_sell[1])<=3) and yb_depth_sell[0][1]-hb_depth_buy[0][1]>max_diff:
    #     max_diff = yb_depth_sell[0][1]-hb_depth_buy[0][1]
    #     trade_info["sell_depth"] = yb_depth_sell
    #     trade_info["buy_depth"] = hb_depth_buy
    #     trade_info["sell_name"] = "YunBi"
    #     trade_info["buy_name"] = "HuoBi"
    #     trade_info["sell_que1"] = ybTradeQue1
    #     trade_info["sell_que2"] = ybTradeQue2
    #     trade_info["buy_que1"] = hbTradeQue1
    #     trade_info["buy_que2"] = hbTradeQue2
    #     trade_info["sell_obj"] = yb
    #     trade_info["buy_obj"]=hb
    # if yb_depth_sell[0][1]-cnbtc_depth_buy[0][1]>spread_threshold_yb_sell_cnbtc_buy and abs(int(cnbtc_depth_buy[1])-int(yb_depth_sell[1])<=3) and yb_depth_sell[0][1]-cnbtc_depth_buy[0][1]>max_diff:
    #     max_diff = yb_depth_sell[0][1]-cnbtc_depth_buy[0][1]
    #     trade_info["sell_depth"] = yb_depth_sell
    #     trade_info["buy_depth"] = cnbtc_depth_buy
    #     trade_info["sell_name"] = "YunBi"
    #     trade_info["buy_name"] = "CNBTC"
    #     trade_info["sell_que1"] = ybTradeQue1
    #     trade_info["sell_que2"] = ybTradeQue2
    #     trade_info["buy_que1"] = cnbtcTradeQue1
    #     trade_info["buy_que2"] = cnbtcTradeQue2
    #     trade_info["sell_obj"] = yb
    #     trade_info["buy_obj"]=cnbtc
    # if cnbtc_depth_sell[0][1]-yb_depth_buy[0][1]>spread_threshold_yb_sell_cnbtc_buy and abs(int(cnbtc_depth_sell[1])-int(yb_depth_buy[1])<=3) and cnbtc_depth_sell[0][1]-yb_depth_buy[0][1]>max_diff:
    #     max_diff = cnbtc_depth_sell[0][1]-yb_depth_buy[0][1]
    #     trade_info["sell_depth"] = cnbtc_depth_sell
    #     trade_info["buy_depth"] = yb_depth_buy
    #     trade_info["sell_name"] = "CNBTC"
    #     trade_info["buy_name"] = "YunBi"
    #     trade_info["sell_que1"] = cnbtcTradeQue1
    #     trade_info["sell_que2"] = cnbtcTradeQue2
    #     trade_info["buy_que1"] = ybTradeQue1
    #     trade_info["buy_que2"] = ybTradeQue2
    #     trade_info["sell_obj"] = cnbtc
    #     trade_info["buy_obj"]=yb
    # if open_okc:
    #     if okc_depth_sell[0][1]-cnbtc_depth_buy[0][1]>spread_threshold_okc_sell_cnbtc_buy and okc_depth_sell[0][1]-cnbtc_depth_buy[0][1]>max_diff:
    #         max_diff = okc_depth_sell[0][1]-cnbtc_depth_buy[0][1]
    #         trade_info["sell_depth"] = okc_depth_sell
    #         trade_info["buy_depth"] = cnbtc_depth_buy
    #         trade_info["sell_name"] = "OKCoin"
    #         trade_info["buy_name"] = "CNBTC"
    #         trade_info["sell_que1"] = okcTradeQue1
    #         trade_info["sell_que2"] = okcTradeQue2
    #         trade_info["buy_que1"] = cnbtcTradeQue1
    #         trade_info["buy_que2"] = cnbtcTradeQue2
    #         trade_info["sell_obj"] = okc
    #         trade_info["buy_obj"]=cnbtc
    #     if cnbtc_depth_sell[0][1]-okc_depth_buy[0][1]>spread_threshold_okc_buy_cnbtc_sell and cnbtc_depth_sell[0][1]-okc_depth_buy[0][1]>max_diff:
    #         max_diff = cnbtc_depth_sell[0][1]-okc_depth_buy[0][1]
    #         trade_info["sell_depth"] = cnbtc_depth_sell
    #         trade_info["buy_depth"] = okc_depth_buy
    #         trade_info["sell_name"] = "CNBTC"
    #         trade_info["buy_name"] = "OKCoin"
    #         trade_info["sell_que1"] = cnbtcTradeQue1
    #         trade_info["sell_que2"] = cnbtcTradeQue2
    #         trade_info["buy_que1"] = okcTradeQue1
    #         trade_info["buy_que2"] = okcTradeQue2
    #         trade_info["buy_obj"] = okc
    #         trade_info["sell_obj"]=cnbtc
    #     if hb_depth_sell[0][1]-okc_depth_buy[0][1]>spread_threshold_okc_buy_hb_sell and hb_depth_sell[0][1]-okc_depth_buy[0][1]>max_diff:
    #         max_diff = hb_depth_sell[0][1]-okc_depth_buy[0][1]
    #         trade_info["sell_depth"] = hb_depth_sell
    #         trade_info["buy_depth"] = okc_depth_buy
    #         trade_info["sell_name"] = "HuoBi"
    #         trade_info["buy_name"] = "OKCoin"
    #         trade_info["sell_que1"] = hbTradeQue1
    #         trade_info["sell_que2"] = hbTradeQue2
    #         trade_info["buy_que1"] = okcTradeQue1
    #         trade_info["buy_que2"] = okcTradeQue2
    #         trade_info["sell_obj"] = hb
    #         trade_info["buy_obj"]=okc
    #     if okc_depth_sell[0][1]-hb_depth_buy[0][1]>spread_threshold_okc_sell_hb_buy and okc_depth_sell[0][1]-hb_depth_buy[0][1]>max_diff:
    #         max_diff = okc_depth_sell[0][1]-hb_depth_buy[0][1]
    #         trade_info["sell_depth"] = okc_depth_sell
    #         trade_info["buy_depth"] = hb_depth_buy
    #         trade_info["sell_name"] = "OKCoin"
    #         trade_info["buy_name"] = "HuoBi"
    #         trade_info["sell_que1"] = okcTradeQue1
    #         trade_info["sell_que2"] = okcTradeQue2
    #         trade_info["buy_que1"] = hbTradeQue1
    #         trade_info["buy_que2"] = hbTradeQue2
    #         trade_info["sell_obj"] = okc
    #         trade_info["buy_obj"]=hb
    #     if yb_depth_sell[0][1]-okc_buy[0][1]>spread_threshold_yb_sell_cnbtc_buy and yb_depth_sell[0][1]-cnbtc_depth_buy[0][1]>max_diff:
    #         max_diff = yb_depth_sell[0][1]-cnbtc_depth_buy[0][1]
    #         trade_info["sell_depth"] = yb_depth_sell
    #         trade_info["buy_depth"] = cnbtc_depth_buy
    #         trade_info["sell_name"] = "YunBi"
    #         trade_info["buy_name"] = "CNBTC"
    #         trade_info["sell_que1"] = ybTradeQue1
    #         trade_info["sell_que2"] = ybTradeQue2
    #         trade_info["buy_que1"] = cnbtcTradeQue1
    #         trade_info["buy_que2"] = cnbtcTradeQue2
    #         trade_info["sell_obj"] = yb
    #         trade_info["buy_obj"]=cnbtc
    #     if cnbtc_depth_sell[0][1]-yb_depth_buy[0][1]>spread_threshold_yb_sell_cnbtc_buy and cnbtc_depth_sell[0][1]-yb_depth_buy[0][1]>max_diff:
    #         max_diff = cnbtc_depth_sell[0][1]-yb_depth_buy[0][1]
    #         trade_info["sell_depth"] = cnbtc_depth_sell
    #         trade_info["buy_depth"] = yb_depth_buy
    #         trade_info["sell_name"] = "CNBTC"
    #         trade_info["buy_name"] = "YunBi"
    #         trade_info["sell_que1"] = cnbtcTradeQue1
    #         trade_info["sell_que2"] = cnbtcTradeQue2
    #         trade_info["buy_que1"] = ybTradeQue1
    #         trade_info["buy_que2"] = ybTradeQue2
    #         trade_info["sell_obj"] = cnbtc
    #         trade_info["buy_obj"]=yb

    # if hb_depth_sell[0][1]-cnbtc_depth_buy[0][1]>spread_threshold_hb_sell_cnbtc_buy and abs(int(cnbtc_depth_buy[1])-int(hb_depth_sell[1])<=3) and hb_depth_sell[0][1]-cnbtc_depth_buy[0][1]>max_diff:
    #     print "start trade major"
    #
    # elif yb_depth_sell[0][1]-cnbtc_depth_buy[0][1]>spread_threshold_yb_sell_cnbtc_buy and abs(int(cnbtc_depth_buy[1])-int(yb_depth_sell[1])<=3):
    #     print 'CNBTC: timestamp:%s  amount:\t%f price:\t%f asks:%s'%(cnbtc_depth_buy[1],cnbtc_depth_buy[0][0],cnbtc_depth_buy[0][1],str(cnbtc_depth_buy[0][2]))
    #     print 'YUNBI: timestamp:%s  amount:\t%f price:\t%f bids:%s'%(yb_depth_sell[1],yb_depth_sell[0][0],yb_depth_sell[0][1],str(yb_depth_sell[0][2]))
    #     print "start trade major"
    #     amount = min(cnbtc_depth_buy[0][0],yb_depth_sell[0][0])*1.0/trade_ratio
    #     amount_buy=amount
    #     amount_sell=amount_buy
    #     limit = (cnbtc_depth_buy[0][1]+yb_depth_sell[0][1])*1.0/2.0
    #     if total_coin>0.0001:
    #         amount_buy = max(amount_buy-total_coin,0)
    #     elif total_coin<-0.0001:
    #         amount_sell = max(amount_sell+total_coin,0)
    #     print "cnbtc buy %f coins at %f and limit %f" %(amount_buy,cnbtc_depth_buy[0][1],limit-lowest_spread_threshold/2.0)
    #     cnbtcTradeQue1.put((cnbtc,"buy",amount_buy,cnbtc_depth_buy[0][1],limit-lowest_spread_threshold/2.0))
    #     print "yb sell %f coins at %f and limit %f" %(amount_sell,yb_depth_sell[0][1],limit+lowest_spread_threshold/2.0)
    #     ybTradeQue1.put((yb,"sell",amount_sell,yb_depth_sell[0][1],limit+lowest_spread_threshold/2.0))
    #     cnbtc_remain = cnbtcTradeQue2.get()
    #     yb_remain = ybTradeQue2.get()
    #     output.write('%f, %f, %f, %f\n'%(yb_remain[0]-amount_sell,amount_buy-cnbtc_remain[0],yb_remain[1],cnbtc_remain[1]))
    #     output.flush()
    #     total_coin+=yb_remain[0]-amount_sell-cnbtc_remain[0]+amount_buy
    #     total_money+=yb_remain[1]+cnbtc_remain[1]
    #     print "cnbtc_remain:%f\t yb_remain:%f,total_remain:%f"%(cnbtc_remain[0],yb_remain[0],maxCoin)
    #     print"coin:%f,money:%f"%(total_coin,total_money)
    #     maxCoin-=max(yb_remain[0],cnbtc_remain[0])
    #     if maxCoin<0:
    #         ybQue1.put(None)
    #         cnbtcQue1.put(None)
    #         ybTradeQue1.put(None)
    #         cnbtcTradeQue1.put(None)
    #         break
    #
    # # elif False:
    # elif cnbtc_depth_sell[0][1]-yb_depth_buy[0][1]>spread_threshold_yb_buy_cnbtc_sell and abs(int(cnbtc_depth_sell[1])-int(yb_depth_buy[1])<=3):
    #     print 'CNBTC: timestamp:%s  amount:\t%f price:\t%f bids:%s'%(cnbtc_depth_sell[1],cnbtc_depth_sell[0][0],cnbtc_depth_sell[0][1],str(cnbtc_depth_sell[0][2]))
    #     print 'YUNBI: timestamp:%s  amount:\t%f price:\t%f asks:%s'%(yb_depth_buy[1],yb_depth_buy[0][0],yb_depth_buy[0][1],str(yb_depth_buy[0][2]))
    #     print "start trade minor"
    #     amount = min(cnbtc_depth_sell[0][0], yb_depth_buy[0][0]) * 1.0 / trade_ratio
    #     amount_buy = amount
    #     amount_sell = amount_buy
    #     limit = (cnbtc_depth_sell[0][1] + yb_depth_buy[0][1]) * 1.0 / 2.0
    #     if total_coin > 0.01:
    #         amount_buy = max(amount_buy - total_coin, 0)
    #     elif total_coin < -0.01:
    #         amount_sell = max(amount_sell + total_coin, 0)
    #     print "cnbtc sell %f coins at %f and limit %f" % (amount_sell, cnbtc_depth_sell[0][1], limit + lowest_spread_threshold/ 2.0)
    #     cnbtcTradeQue1.put((cnbtc, "sell", amount_sell, cnbtc_depth_sell[0][1], limit + lowest_spread_threshold / 2.0))
    #     print "yb buy %f coins at %f and limit %f" % (amount_buy, yb_depth_buy[0][1], limit - lowest_spread_threshold / 2.0)
    #     ybTradeQue1.put(
    #         (yb, "buy", amount_buy, yb_depth_buy[0][1], limit - lowest_spread_threshold / 2.0))
    #     cnbtc_remain = cnbtcTradeQue2.get()
    #     yb_remain = ybTradeQue2.get()
    #     output.write('%f, %f, %f, %f\n' % (
    #     amount_buy - yb_remain[0], cnbtc_remain[0] - amount_sell, yb_remain[1], cnbtc_remain[1]))
    #     total_coin += -yb_remain[0] - amount_sell + cnbtc_remain[0] + amount_buy
    #     total_money += yb_remain[1] + cnbtc_remain[1]
    #     print "cnbtc_remain:%f\t yb_remain:%f,total_remain:%f" % (cnbtc_remain[0], yb_remain[0], maxCoin)
    #     print"coin:%f,money:%f" % (total_coin, total_money)
    #     maxCoin -= max(yb_remain[0], cnbtc_remain[0])
    #     if maxCoin < 0:
    #         ybQue1.put(None)
    #         cnbtcQue1.put(None)
    #         ybTradeQue1.put(None)
    #         cnbtcTradeQue1.put(None)
    #         break
    # # elif False:
    # elif cnbtc_depth_sell[0][1]-hb_depth_buy[0][1]>spread_threshold_hb_buy_cnbtc_sell and abs(int(cnbtc_depth_sell[1])-int(hb_depth_buy[1])<=3):
    #     print 'CNBTC: timestamp:%s  amount:\t%f price:\t%f bids:%s'%(cnbtc_depth_sell[1],cnbtc_depth_sell[0][0],cnbtc_depth_sell[0][1],str(cnbtc_depth_sell[0][2]))
    #     print 'HuoBI: timestamp:%s  amount:\t%f price:\t%f asks:%s'%(hb_depth_buy[1],hb_depth_buy[0][0],hb_depth_buy[0][1],str(hb_depth_buy[0][2]))
    #     print "start trade minor"
    #     amount = min(cnbtc_depth_sell[0][0], hb_depth_buy[0][0]) * 1.0 / trade_ratio
    #     amount_buy = amount
    #     amount_sell = amount_buy
    #     limit = (cnbtc_depth_sell[0][1] + hb_depth_buy[0][1]) * 1.0 / 2.0
    #     if total_coin > 0.01:
    #         amount_buy = max(amount_buy - total_coin, 0)
    #     elif total_coin < -0.01:
    #         amount_sell = max(amount_sell + total_coin, 0)
    #     print "cnbtc sell %f coins at %f and limit %f" % (amount_sell, cnbtc_depth_sell[0][1], limit + lowest_spread_threshold/ 2.0)
    #     cnbtcTradeQue1.put((cnbtc, "sell", amount_sell, cnbtc_depth_sell[0][1], limit + lowest_spread_threshold / 2.0))
    #     print "hb buy %f coins at %f and limit %f" % (amount_buy, hb_depth_buy[0][1], limit - lowest_spread_threshold / 2.0)
    #     hbTradeQue1.put(
    #         (hb, "buy", amount_buy, hb_depth_buy[0][1], limit - lowest_spread_threshold / 2.0))
    #     cnbtc_remain = cnbtcTradeQue2.get()
    #     hb_remain = hbTradeQue2.get()
    #     output.write('%f, %f, %f, %f\n' % (
    #     amount_buy - hb_remain[0], cnbtc_remain[0] - amount_sell, hb_remain[1], cnbtc_remain[1]))
    #     total_coin += -hb_remain[0] - amount_sell + cnbtc_remain[0] + amount_buy
    #     total_money += hb_remain[1] + cnbtc_remain[1]
    #     print "cnbtc_remain:%f\t hb_remain:%f,total_remain:%f" % (cnbtc_remain[0], hb_remain[0], maxCoin)
    #     print"coin:%f,money:%f" % (total_coin, total_money)
    #     maxCoin -= max(hb_remain[0], cnbtc_remain[0])
    #     if maxCoin < 0:
    #         hbQue1.put(None)
    #         cnbtcQue1.put(None)
    #         hbTradeQue1.put(None)
    #         cnbtcTradeQue1.put(None)
    #         break
    # else:
    #     # print "total coin: %f total_cny %f"%(total_eth,total_cny)
    #     # print "yunbi ",str(yb.get_account())
    #     # print "cnbtc ",str(cnbtc.get_account())

# print cnbtc.get_account()
# cnbtc.getDepth()
# print cnbtc.buy(volume=0.01,price=1461)
# print cnbtc.get_account()
# hft = HaiFengTeng.HaiFengTeng(config)
# hft.login()
# yb = YunBi.Yunbi(config,"YunBi2")
# yb.get_account()
# yb.buy(volume=0.001,price=9999.0)
# yb.getOrder()
# print yb.getDepth()

