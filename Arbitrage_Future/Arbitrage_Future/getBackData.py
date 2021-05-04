import OKCoinFuture
import OKCoin
import YunBi
import json
import time
def offset(depth,amount = 7):
    acc = 0
    bids_price = 0
    asks_price = 0
    for g in depth["bids"]:
        acc+=float(g[1])
        bids_price = float(g[0])
        if acc>amount:
            break
    amount = 0
    for g in depth["asks"]:
        acc+=float(g[1])
        asks_price = float(g[0])
        if acc>amount:
            break
    return {"bids":bids_price,"asks":asks_price}
config = json.load(open("config_future.json",'r'))
yb = YunBi.Yunbi(config,currency="btccny")
okc = OKCoin.OKCoin(config,currency='btc_cny')
okcf = OKCoinFuture.OKCoinFuture(config)
backdata = open("log/back_%s.txt"%time.strftime('%Y-%m-%d_%H_%M_%S',time.localtime(time.time())),'a')
tick = 0
change_rate = okcf.exchange_rate()
while True:
    print tick
    tick+=1
    depth ={}
    depth1 = yb.getDepth()
    depth1["asks"].reverse()
    depth["yunbi"] = offset(depth1)
    depth1 = okc.getDepth()
    depth["okc"] = offset(depth1)
    depth1 = okcf.getDepth()
    depth["okcf"] = offset(depth1,amount = 27*7)
    depth["okcf"]["bids"]*=change_rate
    depth["okcf"]["asks"]*=change_rate
    # print depth["okcf"]
    depth["timestamp"] = time.time()
    print depth
    json.dump(depth,backdata,indent=4)
    backdata.flush()
