import numpy as np
import json
last = None
def get_price(ll):
    sum = 0
    for l in ll:
        sum+=float(l[1])
        if sum>.5:
            return float(l[0])
    return l[0]
def get_json(line,reverse = False):
    # print line.strip().split(' ')[1:]
    # print 2
    global last
    s = "".join(line.strip().split(' ')[1:])
    s = s.replace("'", '"').replace("u","")
    # print s
    # print s
    # print s
    try:
        js = json.loads(s)
        if js == None:
            js = last
        else:
            last = js
    except Exception,e:
        # print e
        js = last
    sell = get_price(js["bids"])
    if reverse:
        js['asks'].reverse()
    buy = get_price(js["asks"])
    return sell,buy

def get_price_list(file_name,reverse= False):
    fp = open(file_name)
    polo_btc = fp.readlines()
    buy_list = []
    sell_list = []
    for l in polo_btc:
        sell,buy = get_json(l,reverse)
        buy_list.append(buy)
        sell_list.append(sell)
    return np.asarray(buy_list),np.asarray(sell_list)
    # print js
polo_buy_list,polo_sell_list = get_price_list("log/polo_btc_eth_2017-06-19_04_17_41.txt")
okc_eth_buy_list,okc_eth_sell_list = get_price_list("log/okc_eth_2017-06-19_04_17_41.txt",True)
okc_btc_buy_list,okc_btc_sell_list = get_price_list("log/okc_btc_2017-06-19_04_17_41.txt",True)
# print "12312312",okc_btc_buy_list[6]
print polo_sell_list.shape,okc_btc_buy_list.shape,okc_eth_buy_list.shape
len = 19000
polo_buy_list = polo_buy_list[:len]
polo_sell_list = polo_sell_list[:len]
okc_eth_buy_list = okc_eth_buy_list[:len]
okc_eth_sell_list = okc_eth_sell_list[:len]
okc_btc_buy_list = okc_btc_buy_list[:len]
okc_btc_sell_list = okc_btc_sell_list[:len]
money = 0
space_go = []
space_back = []
times = 0
for i in range(len):
    # print okc_btc_buy_list[i],polo_buy_list[i]
    if okc_btc_sell_list[i]*polo_sell_list[i]*0.999*0.9975 - okc_eth_buy_list[i]/0.999>0:
        money+=okc_btc_sell_list[i]*polo_sell_list[i]*0.999*0.9975 - okc_eth_buy_list[i]/0.999
    elif okc_eth_sell_list[i]*0.999-okc_btc_buy_list[i]/0.999*polo_buy_list[i]/0.9975>0:
        money+=okc_eth_sell_list[i]*0.999-okc_btc_buy_list[i]/0.999*polo_buy_list[i]/0.9975
        if okc_eth_sell_list[i]*0.999-okc_btc_buy_list[i]/0.999*polo_buy_list[i]/0.9975>27:
            times+=1
        # print (okc_eth_sell_list[i]*0.999-okc_btc_buy_list[i]*1.001*polo_buy_list[i]*1.001)/27.0
    space_go.append((okc_btc_sell_list[i]*polo_sell_list[i]*0.999*0.9975 - okc_eth_buy_list[i]/0.999)/27.0)
    space_back.append((okc_eth_sell_list[i]*0.999-okc_btc_buy_list[i]/0.999*polo_buy_list[i]/0.9975)/27.0)
print money
print times
import matplotlib.pyplot as plt
plt.plot(space_go,label='go')
plt.plot([1 for i in space_go])
plt.plot([0 for i in space_go])
plt.plot(space_back,label='back')
plt.legend()
plt.show()