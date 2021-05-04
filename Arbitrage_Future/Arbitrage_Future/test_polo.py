# !/usr/local/bin/python
# -*- coding:utf-8 -*-
import HuoBi
import HuoBiBB
import HuoBiBTC
import OKCoin
import YunBi
import CNBTC
import json
import threading
import Queue
import time
import logging
import numpy
import message
import json
import random
import poloniex
open_platform = [True,True]
numpy.set_printoptions(suppress=True)
history = open("log/historyPrice_%s.txt"%time.strftime('%Y_%m_%d_%H_%M_%S', time.localtime(time.time())),"a")
balance = open("log/balance%s.txt"%time.strftime('%Y_%m_%d %H_%M_%S', time.localtime(time.time())),'a')
ybbtcQue1 = Queue.Queue()
ybbtcQue2 = Queue.Queue()
ybethQue1 = Queue.Queue()
ybethQue2 = Queue.Queue()

poloQue1 = Queue.Queue()
poloQue2 = Queue.Queue()

hbbbQue1 = Queue.Queue()
hbbbQue2 = Queue.Queue()


ybethTradeQue1 = Queue.Queue()
ybethTradeQue2 = Queue.Queue()
ybbtcTradeQue1 = Queue.Queue()
ybbtcTradeQue2 = Queue.Queue()

poloTradeQue1 = Queue.Queue()
poloTradeQue2 = Queue.Queue()

hbbbTradeQue1 = Queue.Queue()
hbbbTradeQue2 = Queue.Queue()

poloAccountQue1 = Queue.Queue()
poloAccountQue2 = Queue.Queue()
ybAccountQue1 = Queue.Queue()
ybAccountQue2 = Queue.Queue()
hbbbAccountQue1 = Queue.Queue()
hbbbAccountQue2 = Queue.Queue()

alertQue = Queue.Queue()

total_trade_coin = 0
delay_time = 0.2
config = json.load(open("config_polo.json","r"))
#####max coin # in each trade
maxTradeLimitation = float(config["MaxCoinTradeLimitation"])
tel_list = config["tel"]
#####max coin # for each account


max_diff_percentage_thres = float(config["max_diff_percentage_thres"])
#######if coin # is lower than alert thres, it will increase the thres
alert_thres_eth = float(config["alert_thres_eth"])
alert_thres_btc = float(config["alert_thres_btc"])
thres_eth = float(config["thres_eth"])
thres_btc = float(config["thres_btc"])
#######max thres increase is slop*alert_thres
slope = float(config["alert_slope"])
# lowest_spread_threshold_minor = float(config["lowest_spread_threshold_minor"])
#####the trade price is max trade limitation*trade ratio behind the min/max price of ask/bid
trade_ratio = float(config["TradeAdvanceRatio"])
# trade_ratio_minor = float(config["TradeAdvanceRatio_minor"])
#####slippage
slippage = float(config["slippage"])
preset_eth_to_btc = float(config["preset_eth_to_btc"])
tmpThresETH = maxTradeLimitation*trade_ratio
tmpThresBTC = maxTradeLimitation*trade_ratio*preset_eth_to_btc
# tmpThres_minor = maxTradeLimitation_minor*trade_ratio
offset_player = int(config["offset_player"])
offset_coin_eth = float(config["offset_coin_eth"])
offset_coin_btc = float(config["offset_coin_btc"])
open_yb = config["open_yunbi"]=='1'
open_hb = config["open_huobi"]=='1'
########return 0 accumulate amount
########return 1 price
########return 2 list
def thresCoin(thres,offset_coin,offset_player,list):
    acc = 0
    for i in range(offset_player,len(list)):
        acc += float(list[i][1])
        if acc > thres+offset_coin:
            return (thres,float(list[i][0]),list)
    return (acc,float(list[-1][0]),list)

def ybethRun():
    while True:
        ybeth = ybethQue1.get()
        if ybeth == None:
            ybethQue1.task_done()
            break
        else:
            while True:
                depth = ybeth.getDepth()
                # print depth
                if depth:
                    break
            depth["asks"].reverse()
            ybethQue2.put((thresCoin(tmpThresETH,offset_coin_eth,offset_player,depth["bids"]),depth["timestamp"]))
            ybethQue2.put((thresCoin(tmpThresETH,offset_coin_eth,offset_player,depth["asks"]),depth["timestamp"]))
        ybethQue1.task_done()

def ybbtcRun():
    while True:
        ybbtc = ybbtcQue1.get()
        if ybbtc == None:
            ybbtcQue1.task_done()
            break
        else:
            while True:
                depth = ybbtc.getDepth()
                if depth:
                    depth["asks"].reverse()
                    break
            ybbtcQue2.put((thresCoin(tmpThresBTC,offset_coin_btc,offset_player,depth["bids"]),depth["timestamp"]))
            ybbtcQue2.put((thresCoin(tmpThresBTC,offset_coin_btc,offset_player,depth["asks"]),depth["timestamp"]))
        ybbtcQue1.task_done()
def hbbbRun():
    while True:
        hbbb = hbbbQue1.get()
        if hbbb == None:
            hbbbQue1.task_done()
            break
        else:
            while True:
                depth = hbbb.getDepth()
                if depth and depth["status"] == "ok":
                    break
            # depth["tick"]["asks"].reverse()
            hbbbQue2.put((thresCoin(tmpThresETH,offset_coin_eth,offset_player,depth["tick"]["bids"]),depth["ts"]/1000))
            hbbbQue2.put((thresCoin(tmpThresETH,offset_coin_eth,offset_player,depth["tick"]["asks"]),depth["ts"]/1000))
        hbbbQue1.task_done()
def poloRun():
    while True:
        polo = poloQue1.get()
        if polo == None:
            poloQue1.task_done()
            break
        else:
            while True:
                depth = polo.getDepth()
                if depth and depth.has_key('bids'):
                    break
            # depth["tick"]["asks"].reverse()
            poloQue2.put(
                (thresCoin(tmpThresETH, offset_coin_eth, offset_player, depth["bids"]), depth["seq"] / 1000))
            poloQue2.put(
                (thresCoin(tmpThresETH, offset_coin_eth, offset_player, depth["asks"]), depth["seq"] / 1000))
        poloQue1.task_done()


#######tradeque1[0]:obj
#######tradeque1[1]:buy or sell
#######tradeque1[2]:amount
#######tradeque1[3]:price
#######tradeque1[4]:limit_price
#######tradeque1[5]:trade_ratio_tmp
def ybethTradeRun():
    while True:
        yb_tuple = ybethTradeQue1.get()
        money = 0
        if yb_tuple == None:
            ybethTradeQue1.task_done()
            break
        yb = yb_tuple[0]
        amount = yb_tuple[2]
        remain = amount
        price = yb_tuple[3]
        if amount==0:
            ybethTradeQue2.put((0.0,0.0))
            ybethTradeQue1.task_done()
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
                        ybethTradeQue2.put((0.0,money))
                        break
                    else:
                        print "yunbi remain buy 0.0"
                        money-=amount*(price+slippage)
                        ybethTradeQue2.put((0.0,money))
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
                        ybethTradeQue2.put((0.0,money))
                        break
            print "get_price"
            while True:
                depth = yb.getDepth()
                if depth:
                    depth["asks"].reverse()
                    break
            if sell:
                price_now = thresCoin(remain*trade_ratio,offset_coin_eth,offset_player,depth["bids"])[1]
                print "price_now yb",price_now,yb_tuple[4]
                if price_now<yb_tuple[4]:
                    ybethTradeQue2.put((remain,money))
                    break
            else:
                price_now = ybThresCoin(remain*trade_ratio,offset_coin_eth,offset_player,depth["asks"])[1]
                print "price_now yb",price_now
                if price_now>yb_tuple[4]:
                    ybethTradeQue2.put((remain,money))
                    break
            price = price_now
            amount = remain
            times-=1
        ybethTradeQue1.task_done()
def ybbtcTradeRun():
    while True:
        yb_tuple = ybbtcTradeQue1.get()
        money = 0
        if yb_tuple == None:
            ybbtcTradeQue1.task_done()
            break
        yb = yb_tuple[0]
        amount = yb_tuple[2]
        remain = amount
        price = yb_tuple[3]
        if amount==0:
            ybbtcTradeQue2.put((0.0,0.0))
            ybbtcTradeQue1.task_done()
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
                        ybbtcTradeQue2.put((0.0,money))
                        break
                    else:
                        print "yunbi remain buy 0.0"
                        money-=amount*(price+slippage)
                        ybbtcTradeQue2.put((0.0,money))
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
                        ybbtcTradeQue2.put((0.0,money))
                        break
            print "get_price"
            while True:
                depth = yb.getDepth()
                if depth:
                    depth["asks"].reverse()
                    break
            if sell:
                price_now = thresCoin(remain*trade_ratio_tmp,offset_coin_btc,offset_player,depth["bids"])[1]
                print "price_now yb",price_now,yb_tuple[4]
                if price_now<yb_tuple[4]:
                    ybbtcTradeQue2.put((remain,money))
                    break
            else:
                price_now = thresCoin(remain*trade_ratio_tmp,offset_coin_btc,offset_player,depth["asks"])[1]
                print "price_now yb",price_now
                if price_now>yb_tuple[4]:
                    ybbtcTradeQue2.put((remain,money))
                    break
            price = price_now
            amount = remain
            times-=1
        ybbtcTradeQue1.task_done()
def poloTradeRun():
    while True:
        polo_tuple = poloTradeQue1.get()
        btc = 0
        if polo_tuple == None:
            poloTradeQue1.task_done()
            break
        polo = polo_tuple[0]
        amount = polo_tuple[2]
        remain = amount
        rate = polo_tuple[3]
        if amount==0:
            poloTradeQue2.put((0.0,0.0))
            poloTradeQue1.task_done()
            continue
        sell = True
        if polo_tuple[1] == "buy":
            sell = False
        times = 10
        while True:
            order = None
            if sell:
                order = polo.sellFillorKill(rate=rate,amount = amount)
            else:
                order = polo.buyFillorKill(rate=rate,amount = amount)
            if order!= None:
                if order.has_key('error'):
                    print "polo",order
                    print "get_price"
                    while True:
                        depth = polo.getDepth()
                        if depth:
                            depth["asks"].reverse()
                            break
                    if sell:
                        price_now = thresCoin(tmpThresETH, offset_coin_eth, offset_player, depth["bids"])[1]
                        print "rate_now polo", price_now, polo_tuple[4]
                    else:
                        price_now = thresCoin(tmpThresETH, offset_coin_eth, offset_player, depth["asks"])[1]
                        print "rate_now polo", price_now, polo_tuple[4]
                    rate = price_now
                    times-=1
                    continue
            else:
		continue
        poloTradeQue1.task_done()
def hbbbTradeRun():
    while True:
        hb_tuple = hbbbTradeQue1.get()
        money = 0
        if hb_tuple == None:
            hbbbTradeQue1.task_done()
            break
        hb = hb_tuple[0]
        amount = hb_tuple[2]
        remain = amount
        price = hb_tuple[3]
        if amount==0:
            hbbbTradeQue2.put((0.0,0.0))
            hbbbTradeQue1.task_done()
            continue
        sell = True
        if hb_tuple[1] == "buy":
            sell = False
        times = 10
        while True:
            order = None
            if sell:
                order = hb.sell(volume = amount,price=price)
                #todo
                if order!=None and order["status"] == "ok":
                    order = hb.place_order(order["data"])
            else:
                #todo
                order = hb.buy(volume = amount, price = price)
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
                        money+=amount*price
                        hbbbTradeQue2.put((0.0,money))
                        break
                    else:
                        print "huobi remain buy 0.0"
                        money-=amount*price
                        hbbbTradeQue2.put((0.0,money))
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
                        money+=float(order["data"]["field-amount"])*price
                        remain = float(order["data"]["amount"])-float(order["data"]["field-amount"])
                        print "huobi remain sell %f"%remain
                    else:
                        money-=float(order["data"]["field-amount"])*price
                        remain = float(order["data"]["amount"])-float(order["data"]["field-amount"])
                        print "huobi remain buy %f"%remain
                    if remain<=0:
                        hbbbTradeQue2.put((0.0,money))
                        break

            print "get_price"
            while True:
                depth = hb.getDepth()
                if depth:
                    break
            if sell:
                price_now = thresCoin(remain*trade_ratio,offset_coin,offset_player,depth['tick']["bids"])[1]
                print "price_now hb",price_now,hb_tuple[4]
                if price_now<hb_tuple[4]:
                    hbbbTradeQue2.put((remain,money))
                    break
            else:
                price_now = thresCoin(remain*trade_ratio,offset_coin,offset_player,depth['tick']["asks"])[1]
                print "price_now hb",price_now
                if price_now>hb_tuple[4]:
                    hbbbTradeQue2.put((remain,money))
                    break
            price = price_now
            amount = remain
            times-=1
        hbbbTradeQue1.task_done()
def ybAccountRun():
    while True:
        yb = ybAccountQue1.get()
        yb_cny = 0
        yb_eth = 0
        yb_btc = 0
        while True:
            yb_acc = yb.get_account()
            if yb_acc!= None:
                if yb_acc.has_key("error"):
                    time.sleep(delay_time)
                    # print yb_acc
                    continue
                break
        for acc in yb_acc["accounts"]:
            if acc["currency"] == "cny":
                yb_cny=float(acc["balance"])
            elif acc["currency"] == "eth":
                yb_eth= float(acc["balance"])
            elif acc["currency"] == "btc":
                yb_btc= float(acc["balance"])

        ybAccountQue1.task_done()
        ybAccountQue2.put((yb_cny,yb_eth,yb_btc))

def poloAccountRun():
    while True:
        polo = poloAccountQue1.get()
        # polo_btc = 0
        # polo_eth = 0
        while True:
            polo_acc = polo.get_account()
            if polo_acc!= None:
                if polo_acc.has_key('error'):
                    # print "polo",polo_acc
                    continue
                break
        polo_eth = float(polo_acc["ETH"])
        polo_btc = float(polo_acc["BTC"])

        poloAccountQue1.task_done()
        poloAccountQue2.put((polo_eth,polo_btc))

def hbbbAccountRun():
    while True:
        hb = hbbbAccountQue1.get()
        hb_eth = 0
        hb_btc = 0
        while True:
            hb_acc = hb.get_account()
            if hb_acc!= None:
                if hb_acc.has_key('code'):
                    continue
                break
        for mon in hb_acc["data"]["list"]:
            if mon["currency"]=="btc" and mon["type"] == "trade":
                hb_btc = float(mon["balance"])
            if mon["currency"] == "eth" and mon["type"] == "trade":
                hb_eth = float(mon["balance"])


        hbbbAccountQue1.task_done()
        hbbbAccountQue2.put((hb_eth,hb_btc))

import sys
import numpy.matlib
def setThreshold(cny_list,eth_list,brokerage_fee,cash_fee,thres_list_now,thres_list_origin,number,price,tick_coin,name_list):
    pass
    # trade_multiplier = numpy.ones([number,number])
    # thres_list = thres_list_origin.copy()
    # sell_times = eth_list/tick_coin
    # buy_times = cny_list/price/tick_coin
    # trade_broker = numpy.add.outer(brokerage_fee,brokerage_fee)*price*1.1
    # trade_cash = numpy.add.outer(cash_fee,numpy.zeros(cash_fee.shape[0]))*price*1.05
    # length = cny_list.shape[0]
    # print "buy_times",buy_times
    # print "sell_times",sell_times
    # tmp = buy_times.copy()
    # tmp[tmp>thres_money] = thres_money
    # tmp = (-tmp+thres_money)*slope
    # tmp[tmp>max_thres_limitation] = max_thres_limitation
    # offset = numpy.matlib.repmat(tmp,length,1)
    # tmp = buy_times.copy()
    # tmp[tmp>thres_money] = thres_money
    # tmp = (-tmp+thres_money)*5/thres_money
    # tmp[tmp>1] = 1
    # max_diff_thres_tmp = max(0,max_diff_thres)
    # tmp_mul = numpy.matlib.repmat(tmp.reshape(length,1),1,length)
    # trade_multiplier+=tmp_mul*trade_multiplier_ratio
    #
    # tmp = numpy.matlib.repmat(tmp.reshape(length,1),1,length)
    # # print 123
    # offset_cash = -numpy.multiply(tmp,numpy.add.outer(cash_fee,numpy.zeros(cash_fee.shape[0]))*price*1.05)
    # # print tmp
    #
    # # tmp = numpy.matlib.repmat(tmp.reshape(length,1),1,length)
    #
    # # print tmp
    # tmp = sell_times.copy()
    # tmp[tmp>thres_coin] = thres_coin
    # tmp = (-tmp+thres_coin)*slope
    # tmp[tmp>max_thres_limitation] = max_thres_limitation
    # offset += numpy.matlib.repmat(tmp.reshape(length,1),1,length)
    #
    # tmp = sell_times.copy()
    # tmp[tmp>thres_coin] = thres_coin
    # tmp = (-tmp+thres_coin)*5/thres_coin
    # tmp[tmp>1] = 1
    # tmp_mul = numpy.matlib.repmat(tmp,length,1)
    # trade_multiplier+=tmp_mul*trade_multiplier_ratio
    # tmp = numpy.matlib.repmat(tmp,length,1)
    # # print 123
    # offset_cash -= numpy.multiply(tmp,numpy.add.outer(cash_fee,numpy.zeros(cash_fee.shape[0]))*price*1.05)
    # # print offset
    # # buy_times<100
    # alertQue.put((buy_times,sell_times,number))
    # # offset[offset<max_diff_thres_tmp] = max_diff_thres_tmp
    # offset[offset>max_thres_limitation] = max_thres_limitation
    # print offset
    # # print offset
    # # print trade_broker,trade_cash,offset_cash
    # thres_list =  trade_broker+trade_cash+offset_cash+max_diff_thres_tmp+offset+thres_list_origin
    # # print thres_list
    # thres_list[:,buy_times<=8] = 999999
    # thres_list[sell_times<=8,:] = 999999
    #  buy_tmp = (thres_money-buy_times.copy())*slope
    # buy_tmp[buy_tmp<0] = 0
    # buy_tmp[buy_tmp>max_diff_thres_tmp] = max_diff_thres_tmp
    # buy_tmp_n_n = numpy.matlib.repmat(buy_tmp.reshape(length, 1), 1, length)
    #
    #
    # sell_tmp = (thres_coin-sell_times.copy())*slope
    # sell_tmp[sell_tmp<0] = 0
    # sell_tmp[sell_tmp>max_diff_thres_tmp] = max_diff_thres_tmp
    #
    #
    # sell_tmp_n_n = numpy.matlib.repmat(sell_tmp,length,1)
    # tmp_n_n = numpy.maximum(sell_tmp_n_n,buy_tmp_n_n)
    # # print thres_list
    # # print tmp_n_n
    # thres_list -= tmp_n_n
    # # thres_list -= sell_tmp
    # numpy.fill_diagonal(thres_list,999999)
    # numpy.fill_diagonal(trade_multiplier,0)
    # trade_multiplier[trade_multiplier>2] = 2
    # # print trade_multiplier
    # # print thres_list
    # # thres_list = numpy.maximum.reduce([thres_list,(trade_broker+trade_cash)])
    # # print buy_times<=1
    # # print thres_list
    # # result = thres_list_origin.copy()
    # # result[:number,:number] = thres_list
    # # thres_list[2,0] = 0
    # # thres_list[2,1] = 0
    # # thres_list[1,2] = 0
    # # thres_list[0,2] = 0
    # # print thres_list
    # return thres_list,trade_multiplier
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
if open_yb:
    ybbtc = YunBi.Yunbi(config,"LiChen","btccny")
    ybeth = YunBi.Yunbi(config,"LiChen","ethcny")
    # print "YB Account "+str(ybbtc.get_account())
else:
    ybbtc = None
    ybeth = None
if open_hb:
    # hbbtc = HuoBiBTC.HuoBiBTC(config,currency="btccny")
    # hbeth = HuoBi.HuoBi(config,currency="ethcny")
    hbbb = HuoBiBB.HuoBi(config)
    # print("HB Account "+str(hbeth.get_account()))
else:
    hbbb = None
polo = poloniex.poloniex(config)
# print "polo Account "+str(polo.get_account())
if open_yb:
    ybbtc_thread = threading.Thread(target=ybbtcRun)
    ybbtc_thread.setDaemon(True)
    ybbtc_thread.start()
    ybeth_thread = threading.Thread(target=ybethRun)
    ybeth_thread.setDaemon(True)
    ybeth_thread.start()
if open_hb:
    hbbb_thread = threading.Thread(target=hbbbRun)
    hbbb_thread.setDaemon(True)
    hbbb_thread.start()
polo_thread = threading.Thread(target=poloRun)
polo_thread.setDaemon(True)
polo_thread.start()
if open_yb:
    ybbtc_trade_thread = threading.Thread(target=ybbtcTradeRun)
    ybbtc_trade_thread.setDaemon(True)
    ybbtc_trade_thread.start()
    ybeth_trade_thread = threading.Thread(target=ybethTradeRun)
    ybeth_trade_thread.setDaemon(True)
    ybeth_trade_thread.start()
if open_hb:
    hbbb_trade_thread = threading.Thread(target=hbbbTradeRun)
    hbbb_trade_thread.setDaemon(True)
    hbbb_trade_thread.start()

polo_trade_thread = threading.Thread(target=poloTradeRun)
polo_trade_thread.setDaemon(True)
polo_trade_thread.start()

if open_yb:
    yb_account_thread = threading.Thread(target=ybAccountRun)
    yb_account_thread.setDaemon(True)
    yb_account_thread.start()
if open_hb:
    hbbb_account_thread = threading.Thread(target=hbbbAccountRun)
    hbbb_account_thread.setDaemon(True)
    hbbb_account_thread.start()
polo_account_thread = threading.Thread(target=poloAccountRun)
polo_account_thread.setDaemon(True)
polo_account_thread.start()

alertThread = threading.Thread(target=alert)
alertThread.setDaemon(True)
alertThread.start()
total_eth = 0
total_btc = 0
total_money = 0
tick = 0
last_total_eth = 0
last_total_btc = 0
last_total_cny = 0
first_total_eth = 0
first_total_btc = 0
first_total_cny = 0
first = True
platform_number = 4
name_list = ["YunBiETH","YunBiBTC","HuoBiBBB","Poloniex"]
obj_list = [ybeth,ybbtc,hbbb,polo]
que1_list = [ybethQue1,ybbtcQue1,hbbbQue1,poloQue1]
que2_list = [ybethQue2,ybbtcQue2,hbbbQue2,poloQue2]
trade_que1_list = [ybethTradeQue1,ybbtcTradeQue1,hbbbTradeQue1,poloTradeQue1]
trade_que2_list = [ybethTradeQue2,ybbtcTradeQue2,hbbbTradeQue2,poloTradeQue2]
has_ts = [True,True,True,True]
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
brokerage_fee = numpy.asarray([0.001,0.002,0.0025])
cash_fee = numpy.asarray([0.001,0.002,0.001])
nokosareta = 0
while True:
    print 'tick',tick
    poloAccountQue1.put(polo)
    if open_yb:
        ybAccountQue1.put(ybeth)
        ybAccountQue1.put(ybbtc)
    if open_hb:
        hbbbAccountQue1.put(hbbb)
    for platform in platform_list:
        if platform["obj"]!=None:
            platform["que1"].put(platform["obj"])
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
            print platform_list[i]["name"],platform_list[i]["depth_buy"][0][1],platform_list[i]["depth_sell"][0][1]
    # average_price /= open_num*2.0/1.01
    # print 'average_price %f'%average_price
    # brokerage_trade = numpy.add.outer(brokerage_fee,brokerage_fee)*average_price
    # cash_trade = numpy.add.outer(cash_fee,numpy.zeros(cash_fee.shape[0]))*average_price

    tick+=1
    if tick % 1 == 0:

        total_cny = 0
        total_eth = 0
        total_btc = 0
        yb_cny = 0
        yb_eth = 0
        yb_btc = 0
        hb_cny = 0
        hb_eth = 0
        hb_btc = 0
        polo_eth = 0
        polo_btc = 0
        if open_yb:
            yb_cny,yb_eth,yb_btc = ybAccountQue2.get()
            print "yb_balance:%f %f %f"%(yb_eth,yb_btc,yb_cny)
        if open_hb:
            hb_eth,hb_btc = hbbbAccountQue2.get()
            hb_cny+=0
            print "hb balance:%f %f %f"%(hb_eth,yb_btc,hb_cny)
        polo_eth,polo_btc = poloAccountQue2.get()
        print "polo balance:%f %f\n" %(polo_eth,polo_btc)
        total_cny = yb_cny+hb_cny
        total_eth = yb_eth+hb_eth+polo_eth
        total_btc = yb_btc+hb_btc+polo_btc
        balance.write("%s %f %f %f %f %f %f %f %f %f %f %f\n"%(time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())),
                                                yb_eth,yb_btc,yb_cny,hb_eth,hb_btc,hb_cny,polo_eth,polo_btc,total_eth,total_btc,total_cny))
        history.write("%s "%time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())))
        for i in range(platform_number):
            if platform_list[i]["obj"]!=None:
                history.write("%f %f "%(platform_list[i]["depth_buy"][0][1],platform_list[i]["depth_sell"][0][1]))
            else:
                history.write('0 0 ')
        history.write('\n')
        balance.flush()
        history.flush()

        cny_list = numpy.asarray([yb_cny,hb_cny])
        eth_list = numpy.asarray([yb_eth,hb_eth,polo_eth])
        btc_list = numpy.asarray([yb_btc,hb_btc,polo_btc])
        last_total_eth = total_eth
        last_total_cny = total_cny
        last_total_btc = total_btc
        if first:
            first_total_cny = total_cny
            first_total_eth = total_eth
            first_total_btc = total_btc
            first = False
    amount = maxTradeLimitation
    polo_buy_eth_ybhb_sell_eth_thres = numpy.asarray([max_diff_percentage_thres,max_diff_percentage_thres])
    polo_sell_eth_ybhb_buy_eth_thres = numpy.asarray([max_diff_percentage_thres,max_diff_percentage_thres])
    if btc_list[2]<amount*preset_eth_to_btc*4:
        polo_buy_eth_ybhb_sell_eth_thres[:]=99999
    if eth_list[2]<amount*4:
        polo_sell_eth_ybhb_buy_eth_thres[:] = 999999
    for i in range(2):
        if btc_list[i]<amount*preset_eth_to_btc*4:
            polo_sell_eth_ybhb_buy_eth_thres[i] = 999999
        if eth_list[i]<amount*4:
            polo_buy_eth_ybhb_sell_eth_thres[i] = 999999
    print "polo_buy_eth_ybhb_sell_eth",polo_buy_eth_ybhb_sell_eth_thres
    print "polo_sell_eth_ybhb_buy_eth",polo_sell_eth_ybhb_buy_eth_thres
    #print platform_list[i]["name"], platform_list[i]["depth_buy"][0][1], platform_list[i]["depth_sell"][0][1]
    diff = -40
    for i in range(1):
        if platform_list[2]["obj"]!=None:
            p_buy = platform_list[3]["depth_buy"][0][1]
            p_sell = platform_list[3]["depth_sell"][0][1]
            hb_buy = platform_list[2]["depth_buy"][0][1]
            hb_sell = platform_list[2]["depth_sell"][0][1]
            amount_hb_buy_p_sell = round(amount*(1-brokerage_fee[1]),6)
            amount_hb_sell_p_buy = amount
            if (hb_sell-p_buy)/p_buy>polo_buy_eth_ybhb_sell_eth_thres[1] and (hb_sell-p_buy)/p_buy>diff:
                diff = (hb_sell-p_buy)/p_buy
                trade_info["sell_price"] = platform_list[2]["depth_sell"][0][1]
                trade_info["sell_amount"] = amount
                trade_info["sell_id"] = 2
                trade_info["sell_platform"] = platform_list[2]["obj"]
                trade_info["buy_price"] = p_buy
                trade_info["buy_id"] = 3
                trade_info["buy_amount"] = amount_hb_sell_p_buy
                trade_info["buy_platform"] = platform_list[3]["obj"]
                trade_info["buy_price"] = platform_list[3]["depth_buy"][0][1]
                trade_info["thres"] = polo_buy_eth_ybhb_sell_eth_thres[1]
                trade_info["diff"] = (hb_sell-p_buy)/p_buy
                trade_info["type"] = "BB"
            elif (hb_buy-p_sell)/hb_buy>polo_sell_eth_ybhb_buy_eth_thres[1] and (p_sell-hb_buy)/hb_buy>diff:
                diff = (p_sell-hb_buy)/hb_buy
                trade_info["sell_price"] = platform_list[3]["depth_sell"][0][1]
                trade_info["sell_amount"] = amount_hb_buy_p_sell
                trade_info["sell_id"] = 3
                trade_info["sell_platform"] = platform_list[3]["obj"]
                trade_info["buy_price"] = p_buy
                trade_info["buy_id"] = 2
                trade_info["buy_amount"] = amount
                trade_info["buy_platform"] = platform_list[2]["obj"]
                trade_info["buy_price"] = platform_list[2]["depth_buy"][0][1]
                trade_info["thres"] = polo_sell_eth_ybhb_buy_eth_thres[1]
                trade_info["diff"] = (p_sell-hb_buy)/hb_buy
                trade_info["type"] = "BB"

    for i in range(1):
        if platform_list[i*2]["obj"]!=None:
            p = platform_list[3]["depth_buy"][0][1]
            p1 = platform_list[3]["depth_sell"][0][1]
            t1 = p*amount/(1-brokerage_fee[2])/(1-brokerage_fee[i])*platform_list[i*2+1]["depth_buy"][0][1]
            t11 = p1*amount/(1-brokerage_fee[2])*(1-brokerage_fee[i])*platform_list[i*2+1]["depth_sell"][0][1]
            t2 = amount*platform_list[i*2]["depth_sell"][0][1]
            t22 = amount*platform_list[i*2]["depth_buy"][0][1]
            print "diff %s sell polo buy: %f"%(platform_list[i*2]["name"],(t2-t1)/t1)
            print "diff %s buy polo sell: %f"%(platform_list[i*2]["name"],(t11-t22)/t22)
	    if (t2-t1)/t1>polo_buy_eth_ybhb_sell_eth_thres[i] and (t2-t1)/t1>diff:
                diff = (t2-t1)/t1
                trade_info["eth_price"] = platform_list[i*2]["depth_sell"][0][1]
                trade_info["eth_type"] = "sell"
                trade_info["eth_amount"] = amount
                trade_info["id"] = i
                trade_info["eth_platform"] = platform_list[i*2]["obj"]
                trade_info["btc_price"] = platform_list[i*2+1]["depth_buy"][0][1]
                trade_info["btc_type"] = "buy"
                trade_info["btc_amount"] = p*amount/(1-brokerage_fee[2])/(1-brokerage_fee[i])-nokosareta
                trade_info["btc_platform"] = platform_list[i*2+1]["obj"]
                trade_info["polo_price"] = p
                trade_info["polo_type"] = "buy"
                trade_info["polo_amount"] = amount/(1-brokerage_fee[2])
                trade_info["thres"] = polo_buy_eth_ybhb_sell_eth_thres[i]
                trade_info["diff"] = (t2-t1)/t1
                trade_info["type"] = "noBB"
                print trade_info
		#json.dump(trade_info,open("log/buy_%d.json"%tick,"w"),indent = 4)

            elif (t11-t22)/t22>polo_sell_eth_ybhb_buy_eth_thres[i] and (t11-t22)/t22>diff:
                diff = (t11-t22)/t22
                trade_info["eth_price"] = platform_list[i*2]["depth_buy"][0][1]
                trade_info["eth_type"] = "buy"
                trade_info["eth_amount"] = amount
                trade_info["id"] = i
                trade_info["eth_platform"] = platform_list[i*2]["obj"]
                trade_info["btc_price"] = platform_list[i*2+1]["depth_sell"][0][1]
                trade_info["btc_type"] = "sell"
                trade_info["btc_amount"] = p1*amount/(1-brokerage_fee[2])*(1-brokerage_fee[i])+nokosareta
                trade_info["btc_platform"] = platform_list[i*2+1]["obj"]
                trade_info["polo_price"] = p1
                trade_info["polo_type"] = "sell"
                trade_info["polo_amount"] = amount/(1-brokerage_fee[i])
                trade_info["thres"] = polo_sell_eth_ybhb_buy_eth_thres[i]
                trade_info["diff"] = (t11-t22)/t11
                trade_info["type"] = "noBB"
		print trade_info
                # json.dump(trade_info,open("log/sell_%d.json"%tick,"w"),indent = 4)
    penalty_ratio = {"buy":1.05,"sell":0.95}
    if diff>-30:
        print "max_diff %f"%diff
        if trade_info["type"] == "noBB":
            platform_id = trade_info["id"]
            eth_amount = round(trade_info["eth_amount"],2)
            btc_amount = round(trade_info["btc_amount"],4)
            polo_amount = round(trade_info["polo_amount"],6)
            trade_que1_list[platform_id*2].put((trade_info["eth_platform"],trade_info["eth_type"],eth_amount,trade_info["eth_price"],trade_info["eth_price"]*penalty_ratio[trade_info["eth_type"]]))
            trade_que1_list[platform_id*2+1].put((trade_info["btc_platform"],trade_info["btc_type"],btc_amount,trade_info["btc_price"],trade_info["btc_price"]*penalty_ratio[trade_info["btc_type"]]))
            trade_que1_list[3].put((polo,trade_info["polo_type"],polo_amount,trade_info["polo_price"],-99999))
            trade_que2_list[platform_id * 2].get()
            trade_que2_list[platform_id * 2+1].get()
            result = trade_que2_list[3].get()
	    print result
            if trade_info["btc_type"] == "buy":
                tmp = btc_amount*(1-brokerage_fee[platform_id])
            else:
                tmp = -btc_amount
            if trade_info["polo_type"]=="sell":
                tmp1 = result[1]*(1-brokerage_fee[2])
            else:
                tmp1 = -result[1]
	    print nokosareta
            #+ is more bt
            #- is less bt
            nokosareta+=tmp+tmp1
            if abs(nokosareta)>0.1:
                print "shit"
                break
        else:
            buy_id = trade_info["buy_id"]
            sell_id = trade_info["sell_id"]
            buy_amount  = trade_info["buy_amount"]
            sell_amount  = trade_info["sell_amount"]
            trade_que1_list[buy_id].put(
                (trade_info["buy_platform"], "buy", buy_amount, trade_info["buy_price"], trade_info["buy_price"]*penalty_ratio["buy"]))
            trade_que1_list[sell_id].put(
                (trade_info["sell_platform"], "sell", sell_amount, trade_info["sell_price"], trade_info["sell_price"]*penalty_ratio["sell"]))
            buy_result = trade_que1_list[buy_id].get()
            sell_resutl = trade_que1_list[sell_id].get()
            # print
            # result = trade_que1_list[3].get()
    else:
        pass
    print("%s %f %f %f %f %f %f %f %f %f %f %f\n"%(time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())),
                                                yb_eth,yb_btc,yb_cny,hb_eth,hb_btc,hb_cny,polo_eth,polo_btc,total_eth,total_btc,total_cny))
