# !/usr/local/bin/python
# -*- coding:utf-8 -*-

import HuoBi
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
import Bitfiniex
import bittrex
open_platform = [True, True, False ,True]
numpy.set_printoptions(suppress=True)
history = open("log/historyPrice_%s.txt" % time.strftime('%Y_%m_%d_%H_%M_%S', time.localtime(time.time())), "a")
balance = open("log/balance%s.txt" % time.strftime('%Y_%m_%d %H_%M_%S', time.localtime(time.time())), 'a')
cnbtcbtcQue1 = Queue.Queue()
cnbtcbtcQue2 = Queue.Queue()
cnbtcethQue1 = Queue.Queue()
cnbtcethQue2 = Queue.Queue()

ybbtcQue1 = Queue.Queue()
ybbtcQue2 = Queue.Queue()
ybethQue1 = Queue.Queue()
ybethQue2 = Queue.Queue()


okcbtcQue1 = Queue.Queue()
okcbtcQue2 = Queue.Queue()
okcethQue1 = Queue.Queue()
okcethQue2 = Queue.Queue()


bfxQue1 = Queue.Queue()
bfxQue2 = Queue.Queue()
btrexQue1 = Queue.Queue()
btrexQue2 = Queue.Queue()


hbbtcQue1 = Queue.Queue()
hbbtcQue2 = Queue.Queue()
hbethQue1 = Queue.Queue()
hbethQue2 = Queue.Queue()


cnbtcethTradeQue1 = Queue.Queue()
cnbtcethTradeQue2 = Queue.Queue()
cnbtcbtcTradeQue1 = Queue.Queue()
cnbtcbtcTradeQue2 = Queue.Queue()

ybethTradeQue1 = Queue.Queue()
ybethTradeQue2 = Queue.Queue()
ybbtcTradeQue1 = Queue.Queue()
ybbtcTradeQue2 = Queue.Queue()

okcethTradeQue1 = Queue.Queue()
okcethTradeQue2 = Queue.Queue()
okcbtcTradeQue1 = Queue.Queue()
okcbtcTradeQue2 = Queue.Queue()

bfxTradeQue1 = Queue.Queue()
bfxTradeQue2 = Queue.Queue()
btrexTradeQue1 = Queue.Queue()
btrexTradeQue2 = Queue.Queue()

hbethTradeQue1 = Queue.Queue()
hbethTradeQue2 = Queue.Queue()
hbbtcTradeQue1 = Queue.Queue()
hbbtcTradeQue2 = Queue.Queue()

bfxAccountQue1 = Queue.Queue()
bfxAccountQue2 = Queue.Queue()
btrexAccountQue1 = Queue.Queue()
btrexAccountQue2 = Queue.Queue()
cnbtcAccountQue1 = Queue.Queue()
cnbtcAccountQue2 = Queue.Queue()

ybAccountQue1 = Queue.Queue()
ybAccountQue2 = Queue.Queue()
hbbtcAccountQue1 = Queue.Queue()
hbbtcAccountQue2 = Queue.Queue()
hbethAccountQue1 = Queue.Queue()
hbethAccountQue2 = Queue.Queue()

okcAccountQue1 = Queue.Queue()
okcAccountQue2 = Queue.Queue()

alertQue = Queue.Queue()

total_trade_coin = 0
delay_time = 0.2
config = json.load(open("config_bfx.json", "r"))
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
eat_market = config["eat_market"]=="1"
preset_eth_to_btc = float(config["preset_eth_to_btc"])
tmpThresETH = maxTradeLimitation * trade_ratio
tmpThresBTC = maxTradeLimitation * trade_ratio * preset_eth_to_btc
# tmpThres_minor = maxTradeLimitation_minor*trade_ratio
offset_player = int(config["offset_player"])
offset_coin_eth = float(config["offset_coin_eth"])
offset_coin_btc = float(config["offset_coin_btc"])
open_yb = config["open_yunbi"] == '1'
open_hb = config["open_huobi"] == '1'
open_okc = config["open_okcoin"] == '1'
open_bfx = config["open_bfx"] == '1'
open_btrex = config["open_btrex"] == '1'
open_cnbtc = config["open_cnbtc"] == '1'


########return 0 accumulate amount
########return 1 price
########return 2 list
def thresCoin(thres, offset_coin, offset_player, list):
    acc = 0
    for i in range(offset_player, len(list)):
        acc += float(list[i][1])
        if acc > thres + offset_coin:
            return (thres, float(list[i][0]), list)
    return (acc, float(list[-1][0]), list)

def thresCoinBFX(thres,offset_coin,offset_player,list):
    acc = 0
    for i in range(offset_player,len(list)):
        acc += float(list[i]["amount"])
        if acc > thres+offset_coin:
            return (acc,float(list[i]["price"]),None)
    return (acc,float(list[-1]["price"]),None)
def thresCoinBTREX(thres,offset_coin,offset_player,list):
    acc = 0
    for i in range(offset_player,len(list)):
        acc += float(list[i]["Quantity"])
        if acc > thres+offset_coin:
            return (acc,float(list[i]["Rate"]),None)
    return (acc,float(list[-1]["Rate"]),None)

def cnbtcethRun():
    while True:
        cnbtc = cnbtcethQue1.get()
        if cnbtc == None:
            cnbtcethQue1.task_done()
            break
        else:
            while True:
                depth = cnbtc.getDepth()
                if depth:
                    break
                print 'cnbtceth',depth
            depth["asks"].reverse()
            cnbtcethQue2.put((thresCoin(tmpThresETH, offset_coin_eth, offset_player, depth["bids"]), depth["timestamp"]))
            cnbtcethQue2.put((thresCoin(tmpThresETH, offset_coin_eth, offset_player, depth["asks"]), depth["timestamp"]))
        cnbtcethQue1.task_done()
def cnbtcbtcRun():
    while True:
        cnbtc = cnbtcbtcQue1.get()
        if cnbtc == None:
            cnbtcbtcQue1.task_done()
            break
        else:
            while True:
                depth = cnbtc.getDepth()
                if depth:
                    break
                print 'cnbtcbtc',depth
            depth["asks"].reverse()
            cnbtcbtcQue2.put((thresCoin(tmpThresBTC, offset_coin_btc, offset_player, depth["bids"]), depth["timestamp"]))
            cnbtcbtcQue2.put((thresCoin(tmpThresBTC, offset_coin_btc, offset_player, depth["asks"]), depth["timestamp"]))
        cnbtcbtcQue1.task_done()
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
                print 'ybeth',depth
            depth["asks"].reverse()
            ybethQue2.put((thresCoin(tmpThresETH, offset_coin_eth, offset_player, depth["bids"]), depth["timestamp"]))
            ybethQue2.put((thresCoin(tmpThresETH, offset_coin_eth, offset_player, depth["asks"]), depth["timestamp"]))
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
                print 'ybbtc',depth
            ybbtcQue2.put((thresCoin(tmpThresBTC, offset_coin_btc, offset_player, depth["bids"]), depth["timestamp"]))
            ybbtcQue2.put((thresCoin(tmpThresBTC, offset_coin_btc, offset_player, depth["asks"]), depth["timestamp"]))
        ybbtcQue1.task_done()

def okcethRun():
    while True:
        okc = okcethQue1.get()
        if okc == None:
            okcethQue1.task_done()
            break
        else:
            while True:
                depth = okc.getDepth()
                if depth:
                    break
                print 'okceth',depth
            depth["asks"].reverse()
            okcethQue2.put((thresCoin(tmpThresETH,offset_coin_eth,offset_player,depth["bids"]),"-99999999"))
            okcethQue2.put((thresCoin(tmpThresETH,offset_coin_eth,offset_player,depth["asks"]),"-99999999"))
        okcethQue1.task_done()


def okcbtcRun():
    while True:
        okc = okcbtcQue1.get()
        if okc == None:
            okcbtcQue1.task_done()
            break
        else:
            while True:
                depth = okc.getDepth()
                if depth:
                    break
                print 'okcbtc',depth
            depth["asks"].reverse()
            okcbtcQue2.put((thresCoin(tmpThresBTC,offset_coin_btc,offset_player,depth["bids"]),"-99999999"))
            okcbtcQue2.put((thresCoin(tmpThresBTC,offset_coin_btc,offset_player,depth["asks"]),"-99999999"))
        okcbtcQue1.task_done()

def hbethRun():
    while True:
        hbeth = hbethQue1.get()
        if hbeth == None:
            hbethQue1.task_done()
            break
        else:
            while True:
                depth = hbeth.getDepth()
                if depth and depth["status"] == "ok":
                    break
                print 'hbeth',depth
            # depth["tick"]["asks"].reverse()
            hbethQue2.put(
                (thresCoin(tmpThresETH, offset_coin_eth, offset_player, depth["tick"]["bids"]), depth["ts"] / 1000))
            hbethQue2.put(
                (thresCoin(tmpThresETH, offset_coin_eth, offset_player, depth["tick"]["asks"]), depth["ts"] / 1000))
        hbethQue1.task_done()


def hbbtcRun():
    while True:
        hbbtc = hbbtcQue1.get()
        if hbbtc == None:
            hbbtcQue1.task_done()
            break
        else:
            while True:
                depth = hbbtc.getDepth()
                # print depth
                # print depth
                if depth and depth.has_key('bids'):
                    break
                print 'hbbtc',depth
            # print depth
            # depth["tick"]["asks"].reverse()
            hbbtcQue2.put((thresCoin(tmpThresBTC, offset_coin_btc, offset_player, depth["bids"]), depth["ts"] / 1000))
            hbbtcQue2.put((thresCoin(tmpThresBTC, offset_coin_btc, offset_player, depth["asks"]), depth["ts"] / 1000))
        hbbtcQue1.task_done()


def bfxRun():
    while True:
        bfx = bfxQue1.get()
        if bfx == None:
            bfxQue1.task_done()
            break
        else:
            while True:
                depth = bfx.getDepth()
                if depth and depth.has_key('bids'):
                    break
                print 'bfx',depth
            # print depth
            # depth["tick"]["asks"].reverse()
            bfxQue2.put(
                (thresCoinBFX(tmpThresETH, offset_coin_eth, offset_player, depth["bids"]), -99999999))
            bfxQue2.put(
                (thresCoinBFX(tmpThresETH, offset_coin_eth, offset_player, depth["asks"]), -9999999))
        bfxQue1.task_done()

def btrexRun():
    while True:
        btrex = btrexQue1.get()
        if btrex == None:
            btrexQue1.task_done()
            break
        else:
            depth = btrex.getDepth(tillOK=True)
            btrexQue2.put(
                (thresCoinBTREX(tmpThresETH, offset_coin_eth, offset_player, depth["result"]["buy"]), -99999999))
            btrexQue2.put(
                (thresCoinBTREX(tmpThresETH, offset_coin_eth, offset_player, depth["result"]["sell"]), -9999999))
        btrexQue1.task_done()
#######tradeque1[0]:obj
#######tradeque1[1]:buy or sell
#######tradeque1[2]:amount
#######tradeque1[3]:price
#######tradeque1[4]:limit_price
#######tradeque1[5]:trade_ratio_tmp

def cnbtcethTradeRun():
    while True:
        cnbtc_tuple = cnbtcethTradeQue1.get()
        if cnbtc_tuple == None:
            cnbtcethTradeQue1.task_done()
            break
        # print cnbtc_tuple
        money = 0;
        cnbtc = cnbtc_tuple[0]
        amount = cnbtc_tuple[2]
        remain = amount
        price = cnbtc_tuple[3]
        if amount == 0:
            cnbtcethTradeQue2.put((0.0, 0.0))
            cnbtcethTradeQue1.task_done()
            continue
        buy = True
        if cnbtc_tuple[1] == "sell":
            buy = False
        times = 10
        while True:
            if buy:
                order = cnbtc.buy(volume=amount, price=price + slippage)
            else:
                order = cnbtc.sell(volume=amount, price=price - slippage)
            if order != None:
                if order.has_key("code") and order["code"] != 1000:
                    time.sleep(delay_time)
                    print "cnbtc", order
                    continue
                id = order["id"]
                wait_times = 5
                while wait_times > 0:
                    wait_times -= 1
                    time.sleep(1)
                    while True:
                        order = cnbtc.getOrder(id)
                        if order != None:
                            break
                    print "cnbtc", order
                    ####2 is done
                    ####
                    if order["status"] == 2:
                        break
                if order["status"] == 2:
                    if buy:
                        print "cnbtc remain buy ", 0.0
                        money -= amount * (price + slippage)
                        cnbtcethTradeQue2.put((0.0, money))
                    else:
                        print "cnbtc remain sell 0.0"
                        money += amount * (price - slippage)
                        cnbtcethTradeQue2.put((0.0, money))
                    break
                elif order["status"] == 0 or order["status"] == 3:
                    while True:
                        order = cnbtc.deleteOrder(id)
                        if order != None:
                            if order.has_key("code") and order["code"] != 1000:
                                print json.dumps(order, ensure_ascii=False)
                                if order["code"] == 3001:
                                    break
                                time.sleep(delay_time)
                                continue
                            break
                    while True:
                        order = cnbtc.getOrder(id)
                        if order != None:
                            # print order
                            if order.has_key("code") and order["code"] != 1000:
                                print "cnbtc", order
                                time.sleep(delay_time)
                                continue
                            # todo judge whether is deleted
                            if order["status"] == 1 or order["status"] == 2:
                                break
                            else:
                                time.sleep(delay_time)
                    print "cnbtc", order
                    if buy:
                        money -= float(order["trade_amount"]) * (price + slippage)
                        remain = float(order["total_amount"]) - float(order["trade_amount"])
                        print "cnbtc remain buy %f/%f" % (remain, float(order["total_amount"]))
                    else:
                        money += float(order["trade_amount"]) * (price - slippage)
                        remain = float(order["total_amount"]) - float(order["trade_amount"])
                        print "cnbtc remain sell %f/%f" % (remain, float(order["total_amount"]))
                    if remain <= 0:
                        cnbtcethTradeQue2.put((0.0, money))
                        break
                else:
                    if buy:
                        money -= float(order["trade_amount"]) * (price + slippage)
                        remain = float(order["total_amount"]) - float(order["trade_amount"])
                        print "cnbtc remain buy %f/%f" % (remain, float(order["total_amount"]))
                    else:
                        money += float(order["trade_amount"]) * (price - slippage)
                        remain = float(order["total_amount"]) - float(order["trade_amount"])
                        print "cnbtc remain sell %f/%f" % (remain, float(order["total_amount"]))
                    if remain <= 0:
                        cnbtcethTradeQue2.put((0.0, money))
                        break
            print "get_depth"
            while True:
                depth = cnbtc.getDepth()
                if depth:
                    break
            depth["asks"].reverse()
            if buy:
                price_now = thresCoin(remain * trade_ratio, offset_coin_eth, offset_player, depth["asks"])[1]
                print "prince_now cnbtc", price_now
            else:
                price_now = thresCoin(remain * trade_ratio, offset_coin_eth, offset_player, depth["bids"])[1]
                print "prince_now cnbtc", price_now
            price = price_now
            amount = remain
            times -= 1
        cnbtcethTradeQue1.task_done()
def cnbtcbtcTradeRun():
    while True:
        cnbtc_tuple = cnbtcbtcTradeQue1.get()
        if cnbtc_tuple == None:
            cnbtcbtcTradeQue1.task_done()
            break
        # print cnbtc_tuple
        money = 0;
        cnbtc = cnbtc_tuple[0]
        amount = cnbtc_tuple[2]
        remain = amount
        price = cnbtc_tuple[3]
        if amount == 0:
            cnbtcbtcTradeQue2.put((0.0, 0.0))
            cnbtcbtcTradeQue1.task_done()
            continue
        buy = True
        if cnbtc_tuple[1] == "sell":
            buy = False
        times = 10
        while True:
            if buy:
                order = cnbtc.buy(volume=amount, price=price + slippage)
            else:
                order = cnbtc.sell(volume=amount, price=price - slippage)
            if order != None:
                if order.has_key("code") and order["code"] != 1000:
                    time.sleep(delay_time)
                    print "cnbtc", order
                    continue
                id = order["id"]
                wait_times = 5
                while wait_times > 0:
                    wait_times -= 1
                    time.sleep(1)
                    while True:
                        order = cnbtc.getOrder(id)
                        if order != None:
                            break
                    print "cnbtc", order
                    ####2 is done
                    ####
                    if order["status"] == 2:
                        break
                if order["status"] == 2:
                    if buy:
                        print "cnbtc remain buy ", 0.0
                        money -= amount * (price + slippage)
                        cnbtcbtcTradeQue2.put((0.0, money))
                    else:
                        print "cnbtc remain sell 0.0"
                        money += amount * (price - slippage)
                        cnbtcbtcTradeQue2.put((0.0, money))
                    break
                elif order["status"] == 0 or order["status"] == 3:
                    while True:
                        order = cnbtc.deleteOrder(id)
                        if order != None:
                            if order.has_key("code") and order["code"] != 1000:
                                print json.dumps(order, ensure_ascii=False)
                                if order["code"] == 3001:
                                    break
                                time.sleep(delay_time)
                                continue
                            break
                    while True:
                        order = cnbtc.getOrder(id)
                        if order != None:
                            # print order
                            if order.has_key("code") and order["code"] != 1000:
                                print "cnbtc", order
                                time.sleep(delay_time)
                                continue
                            # todo judge whether is deleted
                            if order["status"] == 1 or order["status"] == 2:
                                break
                            else:
                                time.sleep(delay_time)
                    print "cnbtc", order
                    if buy:
                        money -= float(order["trade_amount"]) * (price + slippage)
                        remain = float(order["total_amount"]) - float(order["trade_amount"])
                        print "cnbtc remain buy %f/%f" % (remain, float(order["total_amount"]))
                    else:
                        money += float(order["trade_amount"]) * (price - slippage)
                        remain = float(order["total_amount"]) - float(order["trade_amount"])
                        print "cnbtc remain sell %f/%f" % (remain, float(order["total_amount"]))
                    if remain <= 0:
                        cnbtcbtcTradeQue2.put((0.0, money))
                        break
                else:
                    if buy:
                        money -= float(order["trade_amount"]) * (price + slippage)
                        remain = float(order["total_amount"]) - float(order["trade_amount"])
                        print "cnbtc remain buy %f/%f" % (remain, float(order["total_amount"]))
                    else:
                        money += float(order["trade_amount"]) * (price - slippage)
                        remain = float(order["total_amount"]) - float(order["trade_amount"])
                        print "cnbtc remain sell %f/%f" % (remain, float(order["total_amount"]))
                    if remain <= 0:
                        cnbtcbtcTradeQue2.put((0.0, money))
                        break
            print "get_depth"
            while True:
                depth = cnbtc.getDepth()
                if depth:
                    break
            depth["asks"].reverse()
            if buy:
                price_now = thresCoin(remain * trade_ratio, offset_coin_btc, offset_player, depth["asks"])[1]
                print "prince_now cnbtc", price_now
            else:
                price_now = thresCoin(remain * trade_ratio, offset_coin_btc, offset_player, depth["bids"])[1]
                print "prince_now cnbtc", price_now
            price = price_now
            amount = remain
            times -= 1
        cnbtcbtcTradeQue1.task_done()
def ybethTradeRun():
    while True:
        yb_tuple = ybethTradeQue1.get()
        money = 0
        print 'yb tuple', yb_tuple
        if yb_tuple == None:
            ybethTradeQue1.task_done()
            break
        yb = yb_tuple[0]
        amount = yb_tuple[2]
        remain = amount
        price = yb_tuple[3]
        # trade_ratio_tmp = yb_tuple[5]
        if amount == 0:
            ybethTradeQue2.put((0.0, 0.0))
            ybethTradeQue1.task_done()
            continue
        sell = True
        if yb_tuple[1] == "buy":
            sell = False
        times = 10
        while True:
            order = None
            if sell:
                order = yb.sell(volume=amount, price=price - slippage)
            else:
                order = yb.buy(volume=amount, price=price + slippage)
            if order != None:
                if order.has_key("error"):
                    time.sleep(delay_time)
                    print "yb", order
                    continue
                id = order["id"]
                wait_times = 3
                while wait_times > 0:
                    wait_times -= 1
                    time.sleep(1)
                    while True:
                        order = yb.getOrder(id)
                        if order != None:
                            if order.has_key("error"):
                                time.sleep(delay_time)
                                print "yb", order
                                continue
                            break
                    print "yb", order
                    if order["state"] == "done":
                        break
                if order["state"] == "done":
                    if sell:
                        print "yunbi remain sell %f" % 0.0
                        money += amount * (price - slippage)
                        ybethTradeQue2.put((0.0, money))
                        break
                    else:
                        print "yunbi remain buy 0.0"
                        money -= amount * (price + slippage)
                        ybethTradeQue2.put((0.0, money))
                        break
                else:
                    # order["state"] == "wait":
                    while True:
                        order = yb.deleteOrder(id)
                        print "yb", order
                        if order != None:
                            if order.has_key("error"):
                                print "yb,delete", order
                                time.sleep(delay_time)
                                continue
                            break
                    while True:
                        order = yb.getOrder(id)
                        print "yb", order

                        if order != None:
                            if order.has_key("error"):
                                time.sleep(delay_time)
                                print "yb", order
                                continue
                            if order["state"] != "wait":
                                break
                            else:
                                time.sleep(delay_time)
                                # break
                    # todo judge whether has been deleted
                    if sell:
                        money += float(order["executed_volume"]) * (price - slippage)
                        remain = float(order["remaining_volume"])
                        print "yunbi remain sell %f" % float(order["remaining_volume"])
                    else:
                        money -= float(order["executed_volume"]) * (price + slippage)
                        remain = float(order["remaining_volume"])
                        print "yunbi remain buy %f" % float(order["remaining_volume"])
                    if remain <= 0:
                        ybethTradeQue2.put((0.0, money))
                        break
            print "get_price"
            while True:
                depth = yb.getDepth()
                if depth:
                    depth["asks"].reverse()
                    break
            if sell:
                price_now = thresCoin(remain * trade_ratio, offset_coin_eth, offset_player, depth["bids"])[1]
                print "price_now yb", price_now, yb_tuple[4]
                # if price_now < yb_tuple[4]:
                #     ybethTradeQue2.put((remain, money))
                #     break
            else:
                price_now = thresCoin(remain * trade_ratio, offset_coin_eth, offset_player, depth["asks"])[1]
                print "price_now yb", price_now
                # if price_now > yb_tuple[4]:
                #     ybethTradeQue2.put((remain, money))
                #     break
            price = price_now
            amount = remain
            times -= 1
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
        # trade_ratio_tmp = yb_tuple[5]
        if amount == 0:
            ybbtcTradeQue2.put((0.0, 0.0))
            ybbtcTradeQue1.task_done()
            continue
        sell = True
        if yb_tuple[1] == "buy":
            sell = False
        times = 10
        while True:
            order = None
            if sell:
                order = yb.sell(volume=amount, price=price - slippage)
            else:
                order = yb.buy(volume=amount, price=price + slippage)
            if order != None:
                if order.has_key("error"):
                    time.sleep(delay_time)
                    print "yb", order
                    continue
                id = order["id"]
                wait_times = 3
                while wait_times > 0:
                    wait_times -= 1
                    time.sleep(1)
                    while True:
                        order = yb.getOrder(id)
                        if order != None:
                            if order.has_key("error"):
                                time.sleep(delay_time)
                                print "yb", order
                                continue
                            break
                    print "yb", order
                    if order["state"] == "done":
                        break
                if order["state"] == "done":
                    if sell:
                        print "yunbi remain sell %f" % 0.0
                        money += amount * (price - slippage)
                        ybbtcTradeQue2.put((0.0, money))
                        break
                    else:
                        print "yunbi remain buy 0.0"
                        money -= amount * (price + slippage)
                        ybbtcTradeQue2.put((0.0, money))
                        break
                else:
                    # order["state"] == "wait":
                    while True:
                        order = yb.deleteOrder(id)
                        print "yb", order
                        if order != None:
                            if order.has_key("error"):
                                print "yb,delete", order
                                time.sleep(delay_time)
                                continue
                            break
                    while True:
                        order = yb.getOrder(id)
                        print "yb", order

                        if order != None:
                            if order.has_key("error"):
                                time.sleep(delay_time)
                                print "yb", order
                                continue
                            if order["state"] != "wait":
                                break
                            else:
                                time.sleep(delay_time)
                                # break
                    # todo judge whether has been deleted
                    if sell:
                        money += float(order["executed_volume"]) * (price - slippage)
                        remain = float(order["remaining_volume"])
                        print "yunbi remain sell %f" % float(order["remaining_volume"])
                    else:
                        money -= float(order["executed_volume"]) * (price + slippage)
                        remain = float(order["remaining_volume"])
                        print "yunbi remain buy %f" % float(order["remaining_volume"])
                    if remain <= 0:
                        ybbtcTradeQue2.put((0.0, money))
                        break
            print "get_price"
            while True:
                depth = yb.getDepth()
                if depth:
                    depth["asks"].reverse()
                    break
            if sell:
                price_now = \
                thresCoin(remain * trade_ratio, offset_coin_btc, offset_player, depth["bids"])[1]
                print "price_now yb", price_now, yb_tuple[4]
                # if price_now < yb_tuple[4]:
                #     ybbtcTradeQue2.put((remain, money))
                #     break
            else:
                price_now = \
                thresCoin(remain * trade_ratio, offset_coin_btc, offset_player, depth["asks"])[1]
                print "price_now yb", price_now
                # if price_now > yb_tuple[4]:
                #     ybbtcTradeQue2.put((remain, money))
                #     break
            price = price_now
            amount = remain
            times -= 1
        ybbtcTradeQue1.task_done()

def okcbtcTradeRun():
    while True:
        okc_tuple = okcbtcTradeQue1.get()
        money = 0
        if okc_tuple == None:
            okcbtcTradeQue1.task_done()
            break
        okc = okc_tuple[0]
        amount = okc_tuple[2]
        remain = amount
        price = okc_tuple[3]
        if amount==0:
            okcbtcTradeQue2.put((0.0,0.0))
            okcbtcTradeQue1.task_done()
            continue
        sell = True
        if okc_tuple[1] == "buy":
            sell = False
        times = 10
        while True:
            if amount<0.01:
                okcbtcTradeQue2.put((amount,money))
                break
            order = None
            if sell:
                if eat_market:
                    order = okc.sell(volume = amount)
                else:
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
                        okcbtcTradeQue2.put((0.0,money))
                        break
                    else:
                        print "okcoin remain buy 0.0"
                        money-=amount*(price+slippage)
                        okcbtcTradeQue2.put((0.0,money))
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
                        okcbtcTradeQue2.put((0.0,money))
                        break


            print "get_price"
            while True:
                depth = okc.getDepth()
                if depth:
                    depth["asks"].reverse()
                    break
            if sell:
                price_now = thresCoin(remain*trade_ratio,offset_coin_btc,offset_player,depth["bids"])[1]
                print "price_now okc",price_now,okc_tuple[4]
                # if price_now<okc_tuple[4]:
                #     okcbtcTradeQue2.put((remain,money))
                #     break
            else:
                price_now = thresCoin(remain*trade_ratio,offset_coin_btc,offset_player,depth["asks"])[1]
                print "price_now okc",price_now
                # if price_now>okc_tuple[4]:
                #     okcbtcTradeQue2.put((remain,money))
                #     break
            price = price_now
            amount = remain
            times-=1
        okcbtcTradeQue1.task_done()

def okcethTradeRun():
    while True:
        okc_tuple = okcethTradeQue1.get()
        money = 0
        if okc_tuple == None:
            okcethTradeQue1.task_done()
            break
        okc = okc_tuple[0]
        amount = okc_tuple[2]
        remain = amount
        price = okc_tuple[3]
        if amount==0:
            okcethTradeQue2.put((0.0,0.0))
            okcethTradeQue1.task_done()
            continue
        sell = True
        if okc_tuple[1] == "buy":
            sell = False
        times = 10
        while True:
            if amount<0.01:
                okcethTradeQue2.put((amount,money))
                break
            order = None
            if sell:
                if eat_market:
                    order = okc.sell(volume = amount)
                else:
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
                        okcethTradeQue2.put((0.0,money))
                        break
                    else:
                        print "okcoin remain buy 0.0"
                        money-=amount*(price+slippage)
                        okcethTradeQue2.put((0.0,money))
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
                        okcethTradeQue2.put((0.0,money))
                        break


            print "get_price"
            while True:
                depth = okc.getDepth()
                if depth:
                    depth["asks"].reverse()
                    break
            if sell:
                price_now = thresCoin(remain*trade_ratio,offset_coin_eth,offset_player,depth["bids"])[1]
                print "price_now okc",price_now,okc_tuple[4]
                # if price_now<okc_tuple[4]:
                #     okcethTradeQue2.put((remain,money))
                #     break
            else:
                price_now = thresCoin(remain*trade_ratio,offset_coin_eth,offset_player,depth["asks"])[1]
                print "price_now okc",price_now
                # if price_now>okc_tuple[4]:
                #     okcethTradeQue2.put((remain,money))
                #     break
            price = price_now
            amount = remain
            times-=1
        okcethTradeQue1.task_done()
def bfxTradeRun():
    while True:
        bfx_tuple = bfxTradeQue1.get()
        btc = 0
        if bfx_tuple == None:
            bfxTradeQue1.task_done()
            break
        bfx = bfx_tuple[0]
        amount = bfx_tuple[2]
        remain = amount
        rate = bfx_tuple[3]
        if amount == 0:
            bfxTradeQue2.put((0.0, 0.0))
            bfxTradeQue1.task_done()
            continue
        sell = True
        if bfx_tuple[1] == "buy":
            sell = False
        times = 10
        while True:
            order = None
            if sell:
                order = bfx.sell(price=rate, amount=amount,type='exchange market')
            else:
                order = bfx.buy(price=rate, amount=amount,type='exchange market')
            if order != None:
                if order.has_key("id"):
                    id = order["id"]
                else:
                    continue
                while True:
                    order = bfx.getOrder(id,tillOK=True)
                    if float(order["remaining_amount"]) == 0:
                        break
                print order
                price = float(order["avg_execution_price"])
                bfxTradeQue2.put((price,price*amount))
                break
                # print order
                # if order["is_cancelled"]:
                #     print "bfx", order
                #     print "get_price"
                #     while True:
                #         depth = bfx.getDepth()
                #         if depth:
                #             break
                #     if sell:
                #         price_now = thresCoinBFX(tmpThresETH, offset_coin_eth, offset_player, depth["bids"])[1]
                #         print "rate_now bfx", price_now, bfx_tuple[4]
                #     else:
                #         price_now = thresCoinBFX(tmpThresETH, offset_coin_eth, offset_player, depth["asks"])[1]
                #         print "rate_now bfx", price_now
                #     rate = price_now
                #     times -= 1
                #     continue
                # else:
                #     bfxTradeQue2.put((rate, rate * amount))
                #     break
        bfxTradeQue1.task_done()

def btrexTradeRun():
    while True:
        btrex_tuple = btrexTradeQue1.get()
        btc = 0
        if btrex_tuple == None:
            btrexTradeQue1.task_done()
            break
        btrex = btrex_tuple[0]
        amount = btrex_tuple[2]
        remain = amount
        rate = btrex_tuple[3]
        if amount == 0:
            btrexTradeQue2.put((0.0, 0.0))
            btrexTradeQue1.task_done()
            continue
        sell = True
        if btrex_tuple[1] == "buy":
            sell = False
        times = 10
        while True:
            order = None
            if sell:
                order = btrex.sell(rate=rate, amount=amount)
            else:
                order = btrex.buy(rate=rate, amount=amount)
            print order
            if order != None and order.has_key("success") and order["success"]:
                id = order["result"]["uuid"]
                wait_times = 3
                while wait_times>0:
                    wait_times-=1
                    order = btrex.getOrder(id,tillOK=True)
                    print "btrex",order
                    if order["result"]["QuantityRemaining"] == 0:
                        break
                if order["result"]["QuantityRemaining"] == 0:
                    btc+=remain*rate
                    btrexTradeQue2.put((0.0,btc))
                    break
                btrex.deleteOrder(id,tillOK=True)
                order = btrex.getOrder(id,tillOK=True)
                if order["result"]["QuantityRemaining"] == 0:
                    btc+=remain*rate
                    btrexTradeQue2.put((0.0,btc))
                    break
                else:
                    btc += (remain - order["result"]["QuantityRemaining"])*rate
                    remain = order["result"]["QuantityRemaining"]
                depth = btrex.getDepth(tillOK=True)
                if sell:
                    price_now = thresCoinBTREX(tmpThresETH, offset_coin_eth, offset_player, depth["result"]["buy"])[1]
                    print "rate_now btrex", price_now
                else:
                    price_now = thresCoinBTREX(tmpThresETH, offset_coin_eth, offset_player, depth["result"]["sell"])[1]
                    print "rate_now btrex", price_now
                rate = price_now
        btrexTradeQue1.task_done()

def hbethTradeRun():
    while True:
        hb_tuple = hbethTradeQue1.get()
        money = 0
        if hb_tuple == None:
            hbethTradeQue1.task_done()
            break
        hb = hb_tuple[0]
        amount = hb_tuple[2]
        remain = amount
        price = hb_tuple[3]
        if amount == 0:
            hbethTradeQue2.put((0.0, 0.0))
            hbethTradeQue1.task_done()
            continue
        sell = True
        if hb_tuple[1] == "buy":
            sell = False
        times = 10
        while True:
            order = None
            if sell:
                order = hb.sell(volume=amount, price=price - slippage)
                # todo
                if order != None and order["status"] == "ok":
                    order = hb.place_order(order["data"])
            else:
                # todo
                order = hb.buy(volume=amount, price=price + slippage)
                if order != None and order["status"] == "ok":
                    order = hb.place_order(order["data"])
            if order != None:
                if order["status"] != "ok":
                    print "hb", order
                    time.sleep(delay_time)
                    continue
                id = order["data"]
                wait_times = 3
                while wait_times > 0:
                    wait_times -= 1
                    time.sleep(1)
                    while True:
                        order = hb.getOrder(id)
                        if order != None:
                            if order["status"] != "ok":
                                time.sleep(delay_time)
                                print "hb", order
                                continue
                            break
                    print "hb", order
                    if order["data"]["state"] == "filled":
                        break
                # todo
                if order["data"]["state"] == "filled":
                    if sell:
                        print "huobi remain sell %f" % 0.0
                        money += amount * (price - slippage)
                        hbethTradeQue2.put((0.0, money))
                        break
                    else:
                        print "huobi remain buy 0.0"
                        money -= amount * (price + slippage)
                        hbethTradeQue2.put((0.0, money))
                        break
                else:
                    # order["state"] == "wait":
                    while True:
                        print id
                        order = hb.deleteOrder(id)
                        if order != None:
                            if order["status"] != "ok":
                                if order['status'] == 'error' and order['err-code'] == 'order-orderstate-error':
                                    break
                                print "hb", order
                                continue
                            break
                    while True:
                        order = hb.getOrder(id)
                        if order != None:
                            if order["status"] != "ok":
                                time.sleep(delay_time)
                                print "hb", order
                                continue
                            print "hb", order
                            if order["data"]["state"] == "canceled" or order["data"]["state"] == "filled" or \
                                            order["data"]["state"] == "partial-canceled" or order["data"][
                                "state"] == "partial-filled":
                                break
                            else:
                                time.sleep(delay_time)
                    # todo judge whether has been deleted
                    if sell:
                        money += float(order["data"]["field-amount"]) * (price - slippage)
                        remain = float(order["data"]["amount"]) - float(order["data"]["field-amount"])
                        print "huobi remain sell %f" % remain
                    else:
                        money -= float(order["data"]["field-amount"]) * (price + slippage)
                        remain = float(order["data"]["amount"]) - float(order["data"]["field-amount"])
                        print "huobi remain buy %f" % remain
                    if remain <= 0:
                        hbethTradeQue2.put((0.0, money))
                        break

            print "get_price"
            while True:
                depth = hb.getDepth()
                if depth:
                    break
            if sell:
                price_now = thresCoin(remain * trade_ratio, offset_coin_eth, offset_player, depth['tick']["bids"])[1]
                print "price_now hb", price_now, hb_tuple[4]
                # if price_now < hb_tuple[4]:
                #     hbethTradeQue2.put((remain, money))
                #     break
            else:
                price_now = thresCoin(remain * trade_ratio, offset_coin_eth, offset_player, depth['tick']["asks"])[1]
                print "price_now hb", price_now
                # if price_now > hb_tuple[4]:
                #     hbethTradeQue2.put((remain, money))
                #     break
            price = price_now
            amount = remain
            times -= 1
        hbethTradeQue1.task_done()


def hbbtcTradeRun():
    while True:
        hb_tuple = hbbtcTradeQue1.get()
        money = 0
        if hb_tuple == None:
            hbbtcTradeQue1.task_done()
            break
        hb = hb_tuple[0]
        amount = hb_tuple[2]
        remain = amount
        price = hb_tuple[3]
        if amount == 0:
            hbbtcTradeQue2.put((0.0, 0.0))
            hbbtcTradeQue1.task_done()
            continue
        sell = True
        if hb_tuple[1] == "buy":
            sell = False
        times = 10
        while True:
            order = None
            if sell:
                order = hb.sell(volume=amount, price=price - slippage)
                # print order
                # todo
            else:
                # todo
                order = hb.buy(volume=amount, price=price + slippage)
                # print order
            if order != None:
                if order.has_key("code"):
                    print "hb", str(order).encode("utf8")
                    time.sleep(delay_time)
                    continue
                id = order["data"]
                wait_times = 3
                while wait_times > 0:
                    wait_times -= 1
                    time.sleep(1)
                    while True:
                        order = hb.getOrder(id)
                        if order != None:
                            if order.has_key("code"):
                                time.sleep(delay_time)
                                print "hb", str(order).encode("utf8")
                                continue
                            break
                    print "hb", order
                    if order["data"]["state"] == "filled":
                        break
                # todo
                if order["data"]["state"] == "filled":
                    if sell:
                        print "huobi remain sell %f" % 0.0
                        money += amount * (price - slippage)
                        hbbtcTradeQue2.put((0.0, money))
                        break
                    else:
                        print "huobi remain buy 0.0"
                        money -= amount * (price + slippage)
                        hbbtcTradeQue2.put((0.0, money))
                        break
                else:
                    # order["state"] == "wait":
                    while True:
                        print id
                        order = hb.deleteOrder(id)
                        if order != None:
                            if order["status"] != "ok":
                                if order['status'] == 'error' and order['err-code'] == 'order-orderstate-error':
                                    break
                                print "hb", order
                                continue
                            break
                    while True:
                        order = hb.getOrder(id)
                        if order != None:
                            if order["status"] != "ok":
                                time.sleep(delay_time)
                                print "hb", order
                                continue
                            print "hb", order
                            if order["data"]["state"] == "canceled" or order["data"]["state"] == "filled" or \
                                            order["data"]["state"] == "partial-canceled" or order["data"][
                                "state"] == "partial-filled":
                                break
                            else:
                                time.sleep(delay_time)
                    # todo judge whether has been deleted
                    if sell:
                        money += float(order["data"]["field-amount"]) * (price - slippage)
                        remain = float(order["data"]["amount"]) - float(order["data"]["field-amount"])
                        print "huobi remain sell %f" % remain
                    else:
                        money -= float(order["data"]["field-amount"]) * (price + slippage)
                        remain = float(order["data"]["amount"]) - float(order["data"]["field-amount"])
                        print "huobi remain buy %f" % remain
                    if remain <= 0:
                        hbbtcTradeQue2.put((0.0, money))
                        break

            print "get_price"
            while True:
                depth = hb.getDepth()
                if depth:
                    break
            if sell:
                price_now = \
                thresCoin(remain * trade_ratio * preset_eth_to_btc, offset_coin_btc, offset_player, depth["bids"])[1]
                print "price_now hb", price_now, hb_tuple[4]
                # if price_now < hb_tuple[4]:
                #     hbbtcTradeQue2.put((remain, money))
                #     break
            else:
                price_now = \
                thresCoin(remain * trade_ratio * preset_eth_to_btc, offset_coin_btc, offset_player, depth["asks"])[1]
                print "price_now hb", price_now
                # if price_now > hb_tuple[4]:
                #     hbbtcTradeQue2.put((remain, money))
                #     break
            price = price_now
            amount = remain
            times -= 1
        hbbtcTradeQue1.task_done()


def okcAccountRun():
    while True:
        time.sleep(delay_time)
        okc = okcAccountQue1.get()
        while True:
            okc_acc = okc.get_account()
            if okc_acc!= None:
                if okc_acc["result"]!=True:
                    time.sleep(delay_time)
                    # print "okc",okc_acc
                    continue
                break
        okc_eth = float(okc_acc["info"]["funds"]["free"]["eth"])
        okc_cny = float(okc_acc["info"]["funds"]["free"]["cny"])
        okc_btc = float(okc_acc["info"]["funds"]["free"]["btc"])
        # print okc_acc

        okcAccountQue1.task_done()
        okcAccountQue2.put((okc_cny,okc_eth,okc_btc))

def cnbtcAccountRun():
    while True:
        cnbtc = cnbtcAccountQue1.get()
        cnbtc_cny = 0
        cnbtc_eth = 0
        cnbtc_btc = 0
        while True:
            cnbtc_acc = cnbtc.get_account()
            if cnbtc_acc!= None:
                if cnbtc_acc.has_key("code") and cnbtc_acc["code"] != 1000:
                    time.sleep(delay_time)
                    print cnbtc_acc
                    continue
                break
        cnbtc_eth=cnbtc_acc["result"]["balance"]["ETH"]["amount"]
        cnbtc_cny=cnbtc_acc["result"]["balance"]["CNY"]["amount"]
        cnbtc_btc=cnbtc_acc["result"]["balance"]["BTC"]["amount"]

        cnbtcAccountQue1.task_done()
        cnbtcAccountQue2.put((cnbtc_cny,cnbtc_eth,cnbtc_btc))

def ybAccountRun():
    while True:
        yb = ybAccountQue1.get()
        yb_cny = 0
        yb_eth = 0
        yb_btc = 0
        while True:
            yb_acc = yb.get_account()
            # print yb_acc
            if yb_acc != None:
                if yb_acc.has_key("error"):
                    time.sleep(delay_time)
                    # print yb_acc
                    continue
                break
        for acc in yb_acc["accounts"]:
            if acc["currency"] == "cny":
                yb_cny = float(acc["balance"])
            elif acc["currency"] == "eth":
                yb_eth = float(acc["balance"])
            elif acc["currency"] == "btc":
                yb_btc = float(acc["balance"])

        ybAccountQue1.task_done()
        ybAccountQue2.put((yb_cny, yb_eth, yb_btc))


def bfxAccountRun():
    while True:
        bfx = bfxAccountQue1.get()
        bfx_btc = 0
        bfx_eth = 0
        bfx_acc = bfx.get_account(tillOK = True)
        # print bfx_acc
        for i in bfx_acc:
            if i["currency"] == "eth":
                bfx_eth = i["available"]
            if i["currency"] == "btc":
                bfx_btc = i["available"]

        bfxAccountQue1.task_done()
        bfxAccountQue2.put((float(bfx_eth), float(bfx_btc)))

def btrexAccountRun():
    while True:
        btrex = btrexAccountQue1.get()
        btrex_acc = btrex.get_account(tillOK=True)
        for i in btrex_acc["result"]:
            if i["Currency"] == "ETH":
                btrex_eth = i["Available"]
            if i["Currency"] == "BTC":
                btrex_btc = i["Available"]

        btrexAccountQue1.task_done()
        btrexAccountQue2.put((float(btrex_eth), float(btrex_btc)))


def hbbtcAccountRun():
    while True:
        hb = hbbtcAccountQue1.get()
        hb_cny = 0
        hb_eth = 0
        hb_btc = 0
        while True:
            hb_acc = hb.get_account()
            if hb_acc != None:
                # print hb_acc
                if not hb_acc.has_key('available_btc_display'):
                    continue
                break
        hb_btc = float(hb_acc['available_btc_display'])
        hb_cny = float(hb_acc['available_cny_display'])

        hbbtcAccountQue1.task_done()
        hbbtcAccountQue2.put((hb_cny, hb_btc))


def hbethAccountRun():
    while True:
        hb = hbethAccountQue1.get()
        hb_cny = 0
        hb_eth = 0
        hb_btc = 0
        while True:
            hb_acc = hb.get_account()
            if hb_acc != None:
                # print hb_acc
                if hb_acc.has_key('code'):
                    continue
                break
        for mon in hb_acc["data"]["list"]:
            if mon["currency"] == "cny" and mon["type"] == "trade":
                hb_cny = float(mon["balance"])
            if mon["currency"] == "eth" and mon["type"] == "trade":
                hb_eth = float(mon["balance"])

        hbethAccountQue1.task_done()
        hbethAccountQue2.put((hb_cny, hb_eth))


import sys
import numpy.matlib


def setThreshold(cny_list, eth_list, brokerage_fee, cash_fee, thres_list_now, thres_list_origin, number, price,
                 tick_coin, name_list):
    trade_multiplier = numpy.ones([number, number])
    thres_list = thres_list_origin.copy()
    sell_times = eth_list / tick_coin
    buy_times = cny_list / price / tick_coin
    trade_broker = numpy.add.outer(brokerage_fee, brokerage_fee) * price * 1.1
    trade_cash = numpy.add.outer(cash_fee, numpy.zeros(cash_fee.shape[0])) * price * 1.05
    length = cny_list.shape[0]
    print "buy_times", buy_times
    print "sell_times", sell_times
    tmp = buy_times.copy()
    tmp[tmp > thres_money] = thres_money
    tmp = (-tmp + thres_money) * slope
    tmp[tmp > max_thres_limitation] = max_thres_limitation
    offset = numpy.matlib.repmat(tmp, length, 1)
    tmp = buy_times.copy()
    tmp[tmp > thres_money] = thres_money
    tmp = (-tmp + thres_money) * 5 / thres_money
    tmp[tmp > 1] = 1
    max_diff_thres_tmp = max(0, max_diff_thres)
    tmp_mul = numpy.matlib.repmat(tmp.reshape(length, 1), 1, length)
    trade_multiplier += tmp_mul * trade_multiplier_ratio

    tmp = numpy.matlib.repmat(tmp.reshape(length, 1), 1, length)
    # print 123
    offset_cash = -numpy.multiply(tmp, numpy.add.outer(cash_fee, numpy.zeros(cash_fee.shape[0])) * price * 1.05)
    # print tmp

    # tmp = numpy.matlib.repmat(tmp.reshape(length,1),1,length)

    # print tmp
    tmp = sell_times.copy()
    tmp[tmp > thres_coin] = thres_coin
    tmp = (-tmp + thres_coin) * slope
    tmp[tmp > max_thres_limitation] = max_thres_limitation
    offset += numpy.matlib.repmat(tmp.reshape(length, 1), 1, length)

    tmp = sell_times.copy()
    tmp[tmp > thres_coin] = thres_coin
    tmp = (-tmp + thres_coin) * 5 / thres_coin
    tmp[tmp > 1] = 1
    tmp_mul = numpy.matlib.repmat(tmp, length, 1)
    trade_multiplier += tmp_mul * trade_multiplier_ratio
    tmp = numpy.matlib.repmat(tmp, length, 1)
    # print 123
    offset_cash -= numpy.multiply(tmp, numpy.add.outer(cash_fee, numpy.zeros(cash_fee.shape[0])) * price * 1.05)
    # print offset
    # buy_times<100
    alertQue.put((buy_times, sell_times, number))
    # offset[offset<max_diff_thres_tmp] = max_diff_thres_tmp
    offset[offset > max_thres_limitation] = max_thres_limitation
    print offset
    # print offset
    # print trade_broker,trade_cash,offset_cash
    thres_list = trade_broker + trade_cash + offset_cash + max_diff_thres_tmp + offset + thres_list_origin
    # print thres_list
    thres_list[:, buy_times <= 8] = 999999
    thres_list[sell_times <= 8, :] = 999999
    buy_tmp = (thres_money - buy_times.copy()) * slope
    buy_tmp[buy_tmp < 0] = 0
    buy_tmp[buy_tmp > max_diff_thres_tmp] = max_diff_thres_tmp
    buy_tmp_n_n = numpy.matlib.repmat(buy_tmp.reshape(length, 1), 1, length)

    sell_tmp = (thres_coin - sell_times.copy()) * slope
    sell_tmp[sell_tmp < 0] = 0
    sell_tmp[sell_tmp > max_diff_thres_tmp] = max_diff_thres_tmp

    sell_tmp_n_n = numpy.matlib.repmat(sell_tmp, length, 1)
    tmp_n_n = numpy.maximum(sell_tmp_n_n, buy_tmp_n_n)
    # print thres_list
    # print tmp_n_n
    thres_list -= tmp_n_n
    # thres_list -= sell_tmp
    numpy.fill_diagonal(thres_list, 999999)
    numpy.fill_diagonal(trade_multiplier, 0)
    trade_multiplier[trade_multiplier > 2] = 2
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
    return thres_list, trade_multiplier


def alert():
    status_btc = {}
    status_eth = {}
    while True:
        need_alert = 0
        alertTuple = alertQue.get()
        if alertTuple[1]=='btc':
            if not status_btc.has_key(alertTuple[0]):
                if alertTuple[2]>0.5:
                    status_btc[alertTuple[0]]=0
                else:
                    status_btc[alertTuple[0]] = 1
            else:
                if alertTuple[2]>0.5:
                    status_btc[alertTuple[0]]=0
                else:
                    if status_btc[alertTuple[0]] == 0:
                        for tel in tel_list:
                            res = message.send_sms("提醒：%s%s的账户完全没币了" % (alertTuple[0],alertTuple[1]), tel)
                            print res
                    status_btc[alertTuple[0]] = 1
        else:
            if not status_eth.has_key(alertTuple[0]):
                if alertTuple[2]>2:
                    status_eth[alertTuple[0]]=0
                else:
                    status_eth[alertTuple[0]] = 1
            else:
                if alertTuple[2]>2:
                    status_eth[alertTuple[0]]=0
                else:
                    if status_eth[alertTuple[0]] == 0:
                        for tel in tel_list:
                            res = message.send_sms("提醒：%s%s的账户完全没币了" % (alertTuple[0],alertTuple[1]), tel)
                            print res
                    status_eth[alertTuple[0]] = 1
        alertQue.task_done()


import HuoBi
import OKCoin

if open_yb:
    ybbtc = YunBi.Yunbi(config, currency = "btccny")
    ybeth = YunBi.Yunbi(config, currency = "ethcny")
    # print "YB Account "+str(ybbtc.get_account())
else:
    ybeth = None
    ybbtc = None
if open_hb:
    hbbtc = HuoBiBTC.HuoBiBTC(config, currency="btccny")
    hbeth = HuoBi.HuoBi(config, currency="ethcny")
    # print("HB Account "+str(hbeth.get_account()))
else:
    hbbtc = None
    hbeth = None

if open_cnbtc:
    cnbtcbtc = CNBTC.CNBTC(config,currency="btc_cny")
    cnbtceth = CNBTC.CNBTC(config,currency="eth_cny")
else:
    cnbtcbtc = None
    cnbtceth = None
if open_okc:
    okcbtc = OKCoin.OKCoin(config,currency="btc_cny")
    okceth = OKCoin.OKCoin(config,currency="eth_cny")
    okcbtc1 = OKCoin.OKCoin(config,currency="btc_cny",name="OKCoin1")
    okceth1 = OKCoin.OKCoin(config,currency="eth_cny",name="OKCoin1")
    okcbtc2 = OKCoin.OKCoin(config,currency="btc_cny",name="OKCoin2")
    okceth2 = OKCoin.OKCoin(config,currency="eth_cny",name="OKCoin2")
else:
    okcbtc = None
    okceth = None
    okcbtc1 = None
    okceth1 = None
    okcbtc2 = None
    okceth2 = None
if open_bfx:
    bfx = Bitfiniex.BitFiniex(config)
else:
    bfx = None
if open_btrex:
    btrex = bittrex.Bittrex(config)
else:
    btrex = None
# print "bfx Account "+str(bfx.get_account())
if open_cnbtc:
    cnbtcbtc_thread = threading.Thread(target=cnbtcbtcRun)
    cnbtcbtc_thread.setDaemon(True)
    cnbtcbtc_thread.start()
    cnbtceth_thread = threading.Thread(target=cnbtcethRun)
    cnbtceth_thread.setDaemon(True)
    cnbtceth_thread.start()
if open_yb:
    ybbtc_thread = threading.Thread(target=ybbtcRun)
    ybbtc_thread.setDaemon(True)
    ybbtc_thread.start()
    ybeth_thread = threading.Thread(target=ybethRun)
    ybeth_thread.setDaemon(True)
    ybeth_thread.start()
if open_hb:
    hbbtc_thread = threading.Thread(target=hbbtcRun)
    hbbtc_thread.setDaemon(True)
    hbbtc_thread.start()
    hbeth_thread = threading.Thread(target=hbethRun)
    hbeth_thread.setDaemon(True)
    hbeth_thread.start()
if open_okc:
    okcbtc_thread = threading.Thread(target=okcbtcRun)
    okcbtc_thread.setDaemon(True)
    okcbtc_thread.start()
    okceth_thread = threading.Thread(target=okcethRun)
    okceth_thread.setDaemon(True)
    okceth_thread.start()
if open_bfx:
    bfx_thread = threading.Thread(target=bfxRun)
    bfx_thread.setDaemon(True)
    bfx_thread.start()
if open_btrex:
    btrex_thread = threading.Thread(target=btrexRun)
    btrex_thread.setDaemon(True)
    btrex_thread.start()
if open_yb:
    ybbtc_trade_thread = threading.Thread(target=ybbtcTradeRun)
    ybbtc_trade_thread.setDaemon(True)
    ybbtc_trade_thread.start()
    ybeth_trade_thread = threading.Thread(target=ybethTradeRun)
    ybeth_trade_thread.setDaemon(True)
    ybeth_trade_thread.start()
if open_okc:
    okcbtc_trade_thread = threading.Thread(target=okcbtcTradeRun)
    okcbtc_trade_thread.setDaemon(True)
    okcbtc_trade_thread.start()
    okceth_trade_thread = threading.Thread(target=okcethTradeRun)
    okceth_trade_thread.setDaemon(True)
    okceth_trade_thread.start()
if open_hb:
    hbbtc_trade_thread = threading.Thread(target=hbbtcTradeRun)
    hbbtc_trade_thread.setDaemon(True)
    hbbtc_trade_thread.start()
    hbeth_trade_thread = threading.Thread(target=hbethTradeRun)
    hbeth_trade_thread.setDaemon(True)
    hbeth_trade_thread.start()
if open_bfx:
    bfx_trade_thread = threading.Thread(target=bfxTradeRun)
    bfx_trade_thread.setDaemon(True)
    bfx_trade_thread.start()
if open_btrex:
    btrex_trade_thread = threading.Thread(target=btrexTradeRun)
    btrex_trade_thread.setDaemon(True)
    btrex_trade_thread.start()

if open_cnbtc:
    cnbtcbtc_trade_thread = threading.Thread(target=cnbtcbtcTradeRun)
    cnbtcbtc_trade_thread.setDaemon(True)
    cnbtcbtc_trade_thread.start()
    cnbtceth_trade_thread = threading.Thread(target=cnbtcethTradeRun)
    cnbtceth_trade_thread.setDaemon(True)
    cnbtceth_trade_thread.start()
if open_yb:
    yb_account_thread = threading.Thread(target=ybAccountRun)
    yb_account_thread.setDaemon(True)
    yb_account_thread.start()
if open_okc:
    okc_account_thread = threading.Thread(target=okcAccountRun)
    okc_account_thread.setDaemon(True)
    okc_account_thread.start()
if open_hb:
    hbbtc_account_thread = threading.Thread(target=hbbtcAccountRun)
    hbbtc_account_thread.setDaemon(True)
    hbbtc_account_thread.start()
    hbeth_account_thread = threading.Thread(target=hbethAccountRun)
    hbeth_account_thread.setDaemon(True)
    hbeth_account_thread.start()
if open_bfx:
    bfx_account_thread = threading.Thread(target=bfxAccountRun)
    bfx_account_thread.setDaemon(True)
    bfx_account_thread.start()
if open_btrex:
    btrex_account_thread = threading.Thread(target=btrexAccountRun)
    btrex_account_thread.setDaemon(True)
    btrex_account_thread.start()

if open_cnbtc:
    cnbtc_account_thread = threading.Thread(target=cnbtcAccountRun)
    cnbtc_account_thread.setDaemon(True)
    cnbtc_account_thread.start()

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
platform_number_double = 4
platform_number_single = 2
platform_number = platform_number_single+platform_number_double*2
name_list = ["CNBTCCoinETH","CNBTCCoinBTC", "YunBiETH", "YunBiBTC", "HuoBiETH", "HuoBiBTC","OKCoinETH","OKCoinBTC","Bitfinex","Bittrex"]
precision_list = [3,3,2,4,4,4,2,3,3,8]
obj_list = [cnbtceth,cnbtcbtc,ybeth, ybbtc, hbeth, hbbtc,okceth,okcbtc, bfx,btrex]
que1_list = [cnbtcethQue1, cnbtcbtcQue1,ybethQue1, ybbtcQue1, hbethQue1, hbbtcQue1, okcethQue1, okcbtcQue1, bfxQue1,btrexQue1]
que2_list = [cnbtcethQue2, cnbtcbtcQue2,ybethQue2, ybbtcQue2, hbethQue2, hbbtcQue2, okcethQue2, okcbtcQue2, bfxQue2,btrexQue2]
trade_que1_list = [cnbtcethTradeQue1, cnbtcbtcTradeQue1,ybethTradeQue1, ybbtcTradeQue1, hbethTradeQue1, hbbtcTradeQue1, okcethTradeQue1, okcbtcTradeQue1, bfxTradeQue1,btrexTradeQue1]
trade_que2_list = [cnbtcethTradeQue2, cnbtcbtcTradeQue2,ybethTradeQue2, ybbtcTradeQue2, hbethTradeQue2, hbbtcTradeQue2, okcethTradeQue2, okcbtcTradeQue2, bfxTradeQue2,btrexTradeQue2]
has_ts = [True,True,True, True, True, True,False,False, True,False]
origin_fee_type = [True,True,True,True,True,True,True,True,True,False]
platform_list = []
for i in range(platform_number):
    platform_list.append(
        {
            "name": name_list[i],
            "obj": obj_list[i],
            "que1": que1_list[i],
            "que2": que2_list[i],
            "trade_que1": trade_que1_list[i],
            "trade_que2": trade_que2_list[i],
            "depth_buy": None,
            "depth_sell": None,
            "has_ts": has_ts[i],
            "precision":precision_list[i],
            "origin_fee":origin_fee_type[i]
        }
    )
brokerage_fee_btc = numpy.asarray([0.0005, 0.001, 0.002,0.002,0.002,0.0025])
brokerage_fee_eth = numpy.asarray([0.0005, 0.001, 0.002,0.001,0.002,0.0025])
cash_fee = numpy.asarray([0.001,0.001, 0.002,0.001, 0.001,0.001])
nokosareta_eth = 0
nokosareta_btc = 0
calc_money = 0
while True:
    print 'tick', tick
    if open_bfx:
        bfxAccountQue1.put(bfx)
    if open_btrex:
        btrexAccountQue1.put(btrex)
    if open_yb:
        ybAccountQue1.put(ybeth)
    if open_cnbtc:
        cnbtcAccountQue1.put(cnbtceth)
    if open_hb:
        hbethAccountQue1.put(hbeth)
        hbbtcAccountQue1.put(hbbtc)
    if open_okc:
        okcAccountQue1.put(okceth)
        okcAccountQue1.put(okceth1)
        okcAccountQue1.put(okceth2)
    for platform in platform_list:
        if platform["obj"] != None:
            platform["que1"].put(platform["obj"])
    for platform in platform_list:
        if platform["obj"] != None:
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
        if platform_list[i]["obj"] != None:
            # print platform_list[i]
            print platform_list[i]["name"], platform_list[i]["depth_buy"][0][1], platform_list[i]["depth_sell"][0][1]
    # average_price /= open_num*2.0/1.01
    # print 'average_price %f'%average_price
    # brokerage_trade = numpy.add.outer(brokerage_fee,brokerage_fee)*average_price
    # cash_trade = numpy.add.outer(cash_fee,numpy.zeros(cash_fee.shape[0]))*average_price
    # exit()
    tick += 1
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
        okc_cny = 0
        okc_eth = 0
        okc_btc = 0
        bfx_eth = 0
        bfx_btc = 0
        btrex_eth = 0
        btrex_btc = 0
        cnbtc_eth = 0
        cnbtc_btc = 0
        cnbtc_cny = 0
        okc_eth = 0
        okc_btc = 0
        okc_cny = 0
        okc_eth1 = 0
        okc_btc1 = 0
        okc_cny1 = 0
        okc_eth2 = 0
        okc_btc2 = 0
        okc_cny2 = 0
        if open_yb:
            yb_cny, yb_eth, yb_btc = ybAccountQue2.get()
            print "yb_balance:%f %f %f" % (yb_eth, yb_btc, yb_cny)
        if open_cnbtc:
            cnbtc_cny, cnbtc_eth, cnbtc_btc = cnbtcAccountQue2.get()
            print "cnbtc_balance:%f %f %f" % (cnbtc_eth, cnbtc_btc, cnbtc_cny)
        if open_okc:
            okc_cny, okc_eth, okc_btc = okcAccountQue2.get()
            print "okc_balance:%f %f %f" % (okc_eth, okc_btc, okc_cny)
            okc_cny1, okc_eth1, okc_btc1 = okcAccountQue2.get()
            print "okc1_balance:%f %f %f" % (okc_eth1, okc_btc1, okc_cny1)
            okc_cny2, okc_eth2, okc_btc2 = okcAccountQue2.get()
            print "okc2_balance:%f %f %f" % (okc_eth2, okc_btc2, okc_cny2)
            p_eth_norm_sell = platform_list[6]["depth_sell"][0][1]
            p_btc_norm_buy = platform_list[7]["depth_buy"][0][1]
            p_bfx_buy = min(platform_list[8]["depth_buy"][0][1],platform_list[9]["depth_buy"][0][1])
            chooseOKC = 0
            if p_eth_norm_sell/p_btc_norm_buy/p_bfx_buy-1>0.004:
                if okc_btc>50 and okc_btc1>50:
                    chooseOKC = 2
                    platform_list[6]["obj"] = okceth2
                    platform_list[7]["obj"] = okcbtc2
                elif okc_btc>50:
                    chooseOKC = 1
                    platform_list[6]["obj"] = okceth1
                    platform_list[7]["obj"] = okcbtc1
                else:
                    chooseOKC=0
                    platform_list[6]["obj"] = okceth
                    platform_list[7]["obj"] = okcbtc
            print chooseOKC
        if open_hb:
            hb_cny, hb_eth = hbethAccountQue2.get()
            hb_cny1, hb_btc = hbbtcAccountQue2.get()
            hb_cny += hb_cny1
            print "hb balance:%f %f %f" % (hb_eth, yb_btc, hb_cny)
        if open_btrex:
            btrex_eth,btrex_btc = btrexAccountQue2.get()
            print "btrex balance:%f %f" % (btrex_eth, btrex_btc)
        if open_bfx:
            bfx_eth, bfx_btc = bfxAccountQue2.get()
            print "bfx balance:%f %f" % (bfx_eth, bfx_btc)
        total_cny = yb_cny + hb_cny+okc_cny+okc_cny1+okc_cny2+cnbtc_cny
        total_eth = yb_eth + hb_eth + bfx_eth+okc_eth+btrex_eth+okc_eth1+okc_eth2+cnbtc_eth
        total_btc = yb_btc + hb_btc + bfx_btc+okc_btc+btrex_btc+okc_btc1+okc_btc2+cnbtc_btc
        alertQue.put(('Bittrex','btc',btrex_btc))
        alertQue.put(('Bittrex','eth',btrex_eth))
        alertQue.put(('Bitfinex','eth',bfx_eth))
        alertQue.put(('Bitfinex','btc',bfx_btc))
        balance.write(
            "%s %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f\n" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),
                                                       cnbtc_eth,cnbtc_btc,cnbtc_cny,yb_eth, yb_btc, yb_cny, hb_eth, hb_btc, hb_cny, okc_eth, okc_btc, okc_cny, okc_eth1, okc_btc1, okc_cny1,okc_eth2, okc_btc2, okc_cny2, bfx_eth,
                                                       bfx_btc,btrex_eth,btrex_btc, total_eth, total_btc, total_cny))
        history.write("%s " % time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
        for i in range(platform_number):
            if platform_list[i]["obj"] != None:
                history.write("%f %f " % (platform_list[i]["depth_buy"][0][1], platform_list[i]["depth_sell"][0][1]))
            else:
                history.write('0 0 ')
        history.write('\n')
        balance.flush()
        history.flush()

        cny_list = numpy.asarray([cnbtc_cny,yb_cny, hb_cny,okc_cny])
        if open_okc and chooseOKC==2:
            eth_list = numpy.asarray([cnbtc_eth,yb_eth, hb_eth,okc_eth2, bfx_eth,btrex_eth])
            btc_list = numpy.asarray([cnbtc_btc,yb_btc, hb_btc,okc_btc2, bfx_btc,btrex_btc])
        elif open_okc and chooseOKC==1:
            eth_list = numpy.asarray([cnbtc_eth,yb_eth, hb_eth,okc_eth1, bfx_eth,btrex_eth])
            btc_list = numpy.asarray([cnbtc_btc,yb_btc, hb_btc,okc_btc1, bfx_btc,btrex_btc])
        elif open_okc:
            eth_list = numpy.asarray([cnbtc_eth,yb_eth, hb_eth,okc_eth, bfx_eth,btrex_eth])
            btc_list = numpy.asarray([cnbtc_btc,yb_btc, hb_btc,okc_btc, bfx_btc,btrex_btc])
        last_total_eth = total_eth
        last_total_cny = total_cny
        last_total_btc = total_btc
        if first:
            first_total_cny = total_cny
            first_total_eth = total_eth
            first_total_btc = total_btc
            first = False
    amount = maxTradeLimitation
    bfxbtrex_buy_eth_ybhbokc_sell_eth_thres = numpy.asarray([[max_diff_percentage_thres,max_diff_percentage_thres,max_diff_percentage_thres, max_diff_percentage_thres],
                                                        [max_diff_percentage_thres, max_diff_percentage_thres,max_diff_percentage_thres, max_diff_percentage_thres]])
    bfxbtrex_sell_eth_ybhbokc_buy_eth_thres = numpy.asarray([[max_diff_percentage_thres,max_diff_percentage_thres,max_diff_percentage_thres, max_diff_percentage_thres],
                                                        [max_diff_percentage_thres, max_diff_percentage_thres,max_diff_percentage_thres, max_diff_percentage_thres]])
    for j in range(platform_number_double):
        for i in range(platform_number_single):
            bfxbtrex_buy_eth_ybhbokc_sell_eth_thres[i][j]+=brokerage_fee_eth[j]+brokerage_fee_btc[j]+brokerage_fee_eth[platform_number_double+i]
            bfxbtrex_sell_eth_ybhbokc_buy_eth_thres[i][j]+=brokerage_fee_eth[j]+brokerage_fee_btc[j]+brokerage_fee_eth[platform_number_double+i]
    for i in range(platform_number_single):
        if btc_list[platform_number_double+i] < amount * preset_eth_to_btc * 4:
            bfxbtrex_buy_eth_ybhbokc_sell_eth_thres[i,:] = 99999
        if eth_list[platform_number_double+i] < amount * 4:
            bfxbtrex_sell_eth_ybhbokc_buy_eth_thres[i,:] = 999999
    for i in range(platform_number_double):
        if btc_list[i] < amount * preset_eth_to_btc * 4:
            bfxbtrex_sell_eth_ybhbokc_buy_eth_thres[:,i] = 999999
        if eth_list[i] < amount * 4:
            bfxbtrex_buy_eth_ybhbokc_sell_eth_thres[:,i] = 999999
    if btc_list[0]>30:
        bfxbtrex_buy_eth_ybhbokc_sell_eth_thres[0,0] = 999999
        bfxbtrex_buy_eth_ybhbokc_sell_eth_thres[1,0] = 999999
    if btc_list[1]>50:
        bfxbtrex_buy_eth_ybhbokc_sell_eth_thres[0,1] = 999999
        bfxbtrex_buy_eth_ybhbokc_sell_eth_thres[1,1] = 999999
    print "bfxbtrex_buy_eth_ybhbokc_sell_eth", bfxbtrex_buy_eth_ybhbokc_sell_eth_thres
    print "bfxbtrex_sell_eth_ybhbokc_buy_eth", bfxbtrex_sell_eth_ybhbokc_buy_eth_thres
    diff = -40
    for i in range(platform_number_single):
        if platform_list[platform_number_double*2+i]["obj"] == None:
            continue
        for j in range(platform_number_double):
            if platform_list[j*2]["obj"] == None:
                continue
            origin_fee = platform_list[platform_number_double*2+i]["origin_fee"]

            p_bfx_buy = platform_list[platform_number_double*2+i]["depth_buy"][0][1]
            p_eth_norm_sell = platform_list[j*2]["depth_sell"][0][1]
            p_btc_norm_buy = platform_list[j*2+1]["depth_buy"][0][1]
            eth_norm_sell = round(amount,platform_list[j*2]["precision"])
            if origin_fee:
                eth_bfx_buy = round(eth_norm_sell/(1-brokerage_fee_eth[platform_number_double+i]),platform_list[platform_number_double*2+i]["precision"])
                btc_bfx_sell = eth_bfx_buy*p_bfx_buy
            else:
                eth_bfx_buy = round(eth_norm_sell,
                                    platform_list[platform_number_double * 2 + i]["precision"])
                btc_bfx_sell = eth_bfx_buy*p_bfx_buy/(1-brokerage_fee_eth[platform_number_double+i])
            btc_norm_buy = round((btc_bfx_sell+nokosareta_btc)/(1-brokerage_fee_btc[j]),platform_list[j*2+1]["precision"])
            eth_norm_sell = round(eth_norm_sell -nokosareta_eth,platform_list[j*2]["precision"])
            if origin_fee:
                eth_diff = eth_bfx_buy*(1-brokerage_fee_eth[platform_number_double+i]) - eth_norm_sell
            else:
                eth_diff = eth_bfx_buy - eth_norm_sell

            btc_diff = btc_norm_buy*(1-brokerage_fee_btc[j])-btc_bfx_sell
            gain_cny = eth_norm_sell*(1-brokerage_fee_eth[j])*p_eth_norm_sell - btc_norm_buy*p_btc_norm_buy
            exact_gain_cny = gain_cny+eth_diff*p_eth_norm_sell+btc_diff*p_btc_norm_buy
            print p_eth_norm_sell/p_btc_norm_buy/p_bfx_buy-1
            if p_eth_norm_sell/p_btc_norm_buy/p_bfx_buy-1>bfxbtrex_buy_eth_ybhbokc_sell_eth_thres[i][j] and p_btc_norm_buy/p_eth_norm_sell/p_bfx_buy-1 - bfxbtrex_buy_eth_ybhbokc_sell_eth_thres[i][j]>diff:
                print ("如果我想在%s上买%f个eth，此时买的价格为%f，手续费为%f，我将实际买入%f个eth，并且损失%f个btc。\n"
                       "在%s平台上卖%f个eth，价格为%f，手续费是%f，实际上我得到%f块钱\n"
                       "在%s平台上买%f个btc，价格为%f，手续费是%f，实际上我得到%f个btc，以及损失%f块钱\n"
                       "我额外的eth有%f，以及我额外的btc有%f,我赚到%f,实际赚到%f,如果不计算手续费，我能得到%f,手续费成本为%f\n"
                       %(platform_list[platform_number_double*2+i]["name"],eth_bfx_buy,p_bfx_buy,brokerage_fee_btc[platform_number_double+i],eth_bfx_buy*(1-brokerage_fee_btc[platform_number_double+i]),btc_bfx_sell,
                         platform_list[j*2]["name"],eth_norm_sell,p_eth_norm_sell,brokerage_fee_eth[j],eth_norm_sell*(1-brokerage_fee_eth[j])*p_eth_norm_sell,
                         platform_list[j*2+1]["name"],btc_norm_buy,p_btc_norm_buy,brokerage_fee_btc[j],btc_norm_buy*(1-brokerage_fee_btc[j]),btc_norm_buy*p_btc_norm_buy,
                         eth_diff,btc_diff,gain_cny,exact_gain_cny,amount*p_eth_norm_sell-amount*p_bfx_buy*p_btc_norm_buy,amount*p_eth_norm_sell-amount*p_bfx_buy*p_btc_norm_buy-exact_gain_cny))
                diff = p_btc_norm_buy/p_eth_norm_sell/p_bfx_buy - bfxbtrex_buy_eth_ybhbokc_sell_eth_thres[i][j]
                trade_info["eth_price"] = p_eth_norm_sell
                trade_info["eth_type"] = "sell"
                trade_info["eth_amount"] = eth_norm_sell
                trade_info["double_id"] = j
                trade_info["single_id"] = i
                trade_info["origin_fee"] = origin_fee
                trade_info["eth_platform"] = platform_list[j * 2]["obj"]
                trade_info["btc_price"] = p_btc_norm_buy
                trade_info["btc_type"] = "buy"
                trade_info["btc_amount"] = btc_norm_buy
                trade_info["btc_platform"] = platform_list[j * 2 + 1]["obj"]
                trade_info["bfx_platform"] = platform_list[platform_number_double*2+i]["obj"]
                trade_info["bfx_price"] = p_bfx_buy
                trade_info["bfx_type"] = "buy"
                trade_info["bfx_amount"] = eth_bfx_buy
                trade_info["thres"] = bfxbtrex_buy_eth_ybhbokc_sell_eth_thres[i][j]
                trade_info["diff"] = diff
                trade_info["eth_diff"] = eth_diff
                trade_info["btc_diff"] = btc_diff
            else:
                p_bfx_sell = platform_list[platform_number_double*2+i]["depth_sell"][0][1]
                p_eth_norm_buy = platform_list[j * 2]["depth_buy"][0][1]
                p_btc_norm_sell = platform_list[j * 2+1]["depth_sell"][0][1]
                eth_norm_buy = round(amount+nokosareta_eth/(1-brokerage_fee_eth[j]), platform_list[j * 2]["precision"]) #add brokerage
                eth_bfx_sell = round(eth_norm_buy * (1 - brokerage_fee_eth[j]), platform_list[platform_number_double*2+i]["precision"]) #add brokerage
                btc_bfx_buy = eth_bfx_sell * p_bfx_sell * (1 - brokerage_fee_eth[platform_number_double+i])
                btc_norm_sell = round(btc_bfx_buy-nokosareta_btc, platform_list[j * 2 + 1]["precision"])
                eth_diff = eth_norm_buy * (1 - brokerage_fee_eth[j]) - eth_bfx_sell
                eth_norm_buy = round(amount+nokosareta_eth/(1-brokerage_fee_eth[j]), platform_list[j * 2]["precision"]) #add brokerage
                btc_diff = btc_bfx_buy - btc_norm_sell
                gain_cny = btc_norm_sell*(1-brokerage_fee_btc[j]) * p_btc_norm_sell - eth_norm_buy * p_eth_norm_buy
                exact_gain_cny = gain_cny + eth_diff * p_eth_norm_buy + btc_diff * p_btc_norm_sell
                print p_bfx_sell/(p_eth_norm_buy/p_btc_norm_sell)-1
                if p_bfx_sell/(p_eth_norm_buy/p_btc_norm_sell)-1>bfxbtrex_sell_eth_ybhbokc_buy_eth_thres[i][j] and p_bfx_sell/(p_eth_norm_buy/p_btc_norm_sell)-1-bfxbtrex_sell_eth_ybhbokc_buy_eth_thres[i][j]>diff:
                    print ("如果我想在%s上卖%f个eth，此时卖的价格为%f，手续费为%f，实际上得到%f个btc。\n"
                           "在%s平台上买%f个eth，价格为%f，手续费是%f，实际上我得到%f个eth，并且损失%f块钱\n"
                           "在%s平台上卖%f个btc，价格为%f，手续费是%f，实际上我得到%f块钱\n"
                           "我额外的eth有%f，以及我额外的btc有%f,我赚到%f,实际赚到%f,如果不计算手续费，我能得到%f,手续费成本为%f\n"
                           %(platform_list[platform_number_double*2+i]["name"],eth_bfx_sell,p_bfx_sell,brokerage_fee_eth[platform_number_double+i],btc_bfx_buy,
                             platform_list[j*2]["name"],eth_norm_buy,p_eth_norm_buy,brokerage_fee_eth[j],eth_norm_buy*(1-brokerage_fee_eth[j]),eth_norm_buy * p_eth_norm_buy,
                             platform_list[j*2+1]["name"],btc_norm_sell,p_btc_norm_sell,brokerage_fee_btc[j],btc_norm_sell*(1-brokerage_fee_btc[j]) * p_btc_norm_sell,
                             eth_diff,btc_diff,gain_cny,exact_gain_cny,amount*p_btc_norm_sell*p_bfx_sell-amount*p_eth_norm_buy,amount*p_btc_norm_sell*p_bfx_sell-amount*p_eth_norm_buy-exact_gain_cny))
                    diff = p_bfx_sell/(p_eth_norm_buy/p_btc_norm_sell)-1-bfxbtrex_sell_eth_ybhbokc_buy_eth_thres[i][j]
                    trade_info["eth_price"] = p_eth_norm_buy
                    trade_info["eth_type"] = "buy"
                    trade_info["eth_amount"] = eth_norm_buy
                    trade_info["double_id"] = j
                    trade_info["single_id"] = i
                    trade_info["eth_platform"] = platform_list[j * 2]["obj"]
                    trade_info["btc_price"] = p_btc_norm_sell
                    trade_info["btc_type"] = "sell"
                    trade_info["btc_amount"] = btc_norm_sell
                    trade_info["btc_platform"] = platform_list[j * 2 + 1]["obj"]
                    trade_info["bfx_platform"] = platform_list[platform_number_double*2+i]["obj"]
                    trade_info["bfx_price"] = p_bfx_sell
                    trade_info["bfx_type"] = "sell"
                    trade_info["bfx_amount"] = eth_bfx_sell
                    trade_info["thres"] = bfxbtrex_sell_eth_ybhbokc_buy_eth_thres[i][j]
                    trade_info["diff"] = diff
                    trade_info["eth_diff"] = eth_diff
                    trade_info["btc_diff"] = btc_diff
    print 'diff : ', diff
    # exit()
    if diff > -1:
        nokosareta_eth -= trade_info["eth_diff"] ##剩下需要买的
        # nokosareta_btc -= trade_info["btc_diff"] ##剩下需要买的
        if trade_info["eth_type"] == "buy":
            amount = trade_info["eth_amount"]
        print "max_diff %f" % diff
        platform_id = trade_info["double_id"]
        platform_single_id = trade_info["single_id"]
        trade_que1_list[platform_id * 2].put(
            (trade_info["eth_platform"], trade_info["eth_type"], trade_info["eth_amount"], trade_info["eth_price"], -1000))
        trade_que1_list[platform_id * 2 + 1].put(
            (trade_info["btc_platform"], trade_info["btc_type"], trade_info["btc_amount"], trade_info["btc_price"], -1000))
        trade_que1_list[platform_number_double*2+platform_single_id].put((trade_info["bfx_platform"], trade_info["bfx_type"], trade_info["bfx_amount"], trade_info["bfx_price"], -99999))
        result_eth = trade_que2_list[platform_id * 2].get()
        result_btc = trade_que2_list[platform_id * 2 + 1].get()
        calc_money+=result_eth[1]+result_btc[1]
        if result_eth[0]>0:
            if trade_info["eth_type"] == "buy":
                nokosareta_eth+=result_eth[0]* (1 - brokerage_fee_eth[platform_id])
            else:
                nokosareta_eth -= result_eth[0]
        if result_btc[0]>0:
            if trade_info["btc_type"]=="buy":
                nokosareta_btc += result_btc[0]* (1 - brokerage_fee_btc[platform_id])
            else:
                nokosareta_btc -= result_btc[0]
        result = trade_que2_list[platform_number_double*2+platform_single_id].get()
        if trade_info["btc_type"] == "buy":
            tmp = trade_info["btc_amount"] * (1 - brokerage_fee_btc[platform_id])
        else:
            tmp = -trade_info["btc_amount"]
        if trade_info["bfx_type"] == "sell":
            tmp1 = result[1] * (1 - brokerage_fee_eth[platform_number_double+platform_single_id])
        else:
            if origin_fee:
                tmp1 = - result[1]
            else:
                tmp1 = -result[1]/(1 - brokerage_fee_eth[platform_number_double+platform_single_id])
        print "这次交易由于%s平台而增加了%f个btc，由于%s平台而增加了%f个btc，所以，要额外买入%f个btc"%(platform_list[platform_id*2+1]["name"],tmp,platform_list[platform_number_double*2+platform_single_id]["name"],tmp1,-(tmp+tmp1))
        nokosareta_btc -= tmp + tmp1
        if abs(nokosareta_btc) > 0.1:
            print "shit"
            break
            # if maxCoin<0:
            #     hbQue1.put(None)
            #     cnbtcQue1.put(None)
            #     hbTradeQue1.put(None)
            #     cnbtcTradeQue1.put(None)
            #     break
    else:
        pass
    print "残留的需要买入的eth个数为%f,残留的需要买入的btc个数为%f"%(nokosareta_eth,nokosareta_btc)
    print("%s %f %f %f %f %f %f %f\n" % (time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())),
                                                     total_eth, total_btc, total_cny,last_total_eth-first_total_eth,last_total_btc-first_total_btc,last_total_cny-first_total_cny,calc_money))
