import YunBi
import CNBTC
import HuoBi
import json
import OKCoin
import poloniex
import poloniex
import time
config = json.load(open("config.json","r"))
fp_hb_eth = open("log/hb_eth_%s.txt"%(time.strftime('%Y-%m-%d_%H_%M_%S',time.localtime(time.time()))),'a')
fp_okc_eth = open("log/okc_eth_%s.txt"%(time.strftime('%Y-%m-%d_%H_%M_%S',time.localtime(time.time()))),'a')
fp_hb_btc = open("log/hb_btc_%s.txt"%(time.strftime('%Y-%m-%d_%H_%M_%S',time.localtime(time.time()))),'a')
fp_okc_btc = open("log/okc_btc_%s.txt"%(time.strftime('%Y-%m-%d_%H_%M_%S',time.localtime(time.time()))),'a')
fp_polo_btc_eth = open("log/polo_btc_eth_%s.txt"%(time.strftime('%Y-%m-%d_%H_%M_%S',time.localtime(time.time()))),'a')
fp_time_stamp = open("log/time_stamp_%s.txt"%(time.strftime('%Y-%m-%d_%H_%M_%S',time.localtime(time.time()))),'a')
# print "config",config
# def run():
#     while True:
#         print 1
# import threading
# th = threading.Thread(target=run)
# th.setDaemon(True)
# th.start()
# while True:
#     pass

polon = poloniex.poloniex(config)
# print poloniex.get_account()
# print polon.getDepth('BTC_ETH')
hb_btc = HuoBi.HuoBi(config,currency="btccny")
hb_eth = HuoBi.HuoBi(config)
okc_btc = OKCoin.OKCoin(config,currency="btc_cny")
okc_eth = OKCoin.OKCoin(config)
i = 0
while True:
    i+=1
    print i
    try:
        fp_hb_btc.write("%d %s\n"%(i,str(hb_btc.getDepth("step5"))))
        fp_hb_eth.write("%d %s\n"%(i,str(hb_btc.getDepth_BTC())))
        fp_okc_btc.write("%d %s\n"%(i,str(okc_btc.getDepth())))
        fp_okc_eth.write("%d %s\n"%(i,str(okc_eth.getDepth())))
        fp_polo_btc_eth.write("%d %s\n"%(i,polon.getDepth('BTC_ETH')))
        fp_time_stamp.write("%d %d\n"%(i,int(time.time())))
        fp_hb_eth.flush()
        fp_time_stamp.flush()
        fp_hb_btc.flush()
        fp_okc_btc.flush()
        fp_okc_eth.flush()
        fp_polo_btc_eth.flush()
    except Exception,e:
        print e
# fp_polo_btc_eth.write("%s\n")%str(okc_eth.getDepth())
# print okc.getDepth()
# hb = HuoBi.HuoBi(config)

# yb = YunBi.Yunbi(config,"YunBi2")
# okc = OKCoin.OKCoin(config)
# cnbtc = CNBTC.CNBTC(config)
# pn = poloniex.poloniex("123","123")
# print pn.returnTicker()
# print hb.getOrder('211726')
# print hb.deleteOrder('211726')
# res = yb.trades()
# res = hb.getDepth()
# res = hb.get_account()
# res = hb.get_balance()
# res = hb.sell(0.001,1000000)
# res = okc.getDepth()
# print res
# res = okc.get_account()
# import random
# print int((random.random()-0.5)*2*0.04*100)/100.0+0.4
# print res
# res = okc.sell(volume="0.0001")
# print res
# while(True):
#     print ("\a")
# import numpy as np
# import logging
# import time
# import time
# time1 = time.time()
# time.sleep(15)
# time2 = time.time()
# print time2 - time1
# logging.error("test")
# logging.log("DATA","sdfsdf")
# for k in res:
# result =  cnbtc.buy(volume="0.001",price=1500.0)
# if result["code"]==1000:
#     id = result["id"]
#     while True:
#         print cnbtc.getOrder(id)
# yb.sell(volume=0.001,price=1430.0)
# while True:
#     yb.getOrder()
# order = yb.sell(volume=0.0001,price=999999.0)
# if order != None:
#     yb.getOrder(order["id"])
# yb.deleteOrder("426677898")
# yb.getOrder("426677898")
