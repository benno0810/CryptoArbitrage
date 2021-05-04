import YunBi
import CNBTC
import json
import threading
import Queue
import time
history = open("historyPrice.txt","a")
ybQue1 = Queue.Queue()
ybQue2 = Queue.Queue()
cnbtcQue1 = Queue.Queue()
cnbtcQue2 = Queue.Queue()
config = json.load(open("config.json","r"))
#####max coin # in each trade
maxTradeLimitation = float(config["MaxCoinTradeLimitation"])
maxTradeLimitation_minor = float(config["MaxCoinTradeLimitation_minor"])
#####max coin # for each account
maxCoin = float(config["MaxCoinLimitation"])
#####if spread over this threshold, we trade
spread_threshold = float(config["spread_threshold"])
spread_threshold_minor = float(config["spread_threshold_minor"])
#####if we start a trade, we will accept all trade until spread reach lowest spread threshold, after that, we cancel all trade
lowest_spread_threshold = float(config["lowest_spread_threshold"])
lowest_spread_threshold_minor = float(config["lowest_spread_threshold_minor"])
#####the trade price is max trade limitation*trade ratio behind the min/max price of ask/bid
trade_ratio = float(config["TradeAdvanceRatio"])
trade_ratio_minor = float(config["TradeAdvanceRatio_minor"])
#####slippage
slippage = float(config["slippage"])
tmpThres = maxTradeLimitation*trade_ratio
tmpThres_minor = maxTradeLimitation_minor*trade_ratio_minor
offset_player = int(config["offset_player"])
offset_player_minor = int(config["offset_player_minor"])
offset_coin = float(config["offset_coin"])
offset_coin_minor = float(config["offset_coin_minor"])
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
            ybQue2.put((ybThresCoin(tmpThres_minor,offset_coin_minor,offset_player_minor,depth["asks"]),depth["timestamp"]))
        ybQue1.task_done()
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
            cnbtcQue2.put((cnbtcThresCoin(tmpThres,offset_coin,offset_player,depth["asks"]),depth["timestamp"]))
            cnbtcQue2.put((cnbtcThresCoin(tmpThres_minor,offset_coin_minor,offset_player_minor,depth["bids"]),depth["timestamp"]))
        cnbtcQue1.task_done()

yb = YunBi.Yunbi(config,"LiChen")
# print yb.get_account()
cnbtc = CNBTC.CNBTC(config)
# print cnbtc.get_account()
yb_thread = threading.Thread(target=ybRun)
yb_thread.start()
cnbtc_thread = threading.Thread(target=cnbtcRun)
cnbtc_thread.start()
tick = 0
while True:
    print 'tick',tick
    cnbtcQue1.put(cnbtc)
    ybQue1.put(yb)
    yb_depth = ybQue2.get()
    cnbtc_depth = cnbtcQue2.get()
    yb_depth_minor = ybQue2.get()
    cnbtc_depth_minor = cnbtcQue2.get()
    ###depth[0] is amount
    ###depth[1] is price
    ###depth[2] is list
    print "forward   yb:%10f cnbtc:%10f diff:%10f"%(yb_depth[0][1],cnbtc_depth[0][1],yb_depth[0][1]-cnbtc_depth[0][1])
    print "backward  yb:%10f cnbtc:%10f diff:%10f"%(yb_depth_minor[0][1],cnbtc_depth_minor[0][1],cnbtc_depth_minor[0][1]-yb_depth_minor[0][1])
    tick+=1
    history.write("%s %f %f %f %f %f %f\n"%(time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())),
                                                yb_depth[0][1],cnbtc_depth[0][1],yb_depth[0][1]-cnbtc_depth[0][1],yb_depth_minor[0][1],cnbtc_depth_minor[0][1],cnbtc_depth_minor[0][1]-yb_depth_minor[0][1]))
    # history.write("%s %f %f %f\n"%(time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(time.time())),

    history.flush()


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

