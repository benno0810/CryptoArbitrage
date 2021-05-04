import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
fp = open("log/back_2017-07-22_23_37_13.txt")
s = fp.read()
data = json.loads('['+s.replace('}{','},{')+']')
reform = [{"timestamp":x["timestamp"],
           "yunbi_bids":x["yunbi"]["bids"],
           "yunbi_asks":x["yunbi"]["asks"],
           "okc_bids":x["okc"]["bids"],
           "okc_asks":x["okc"]["asks"],
           "okcf_bids":x["okcf"]["bids"],
           "okcf_asks":x["okcf"]["asks"],}for x in data]
data =  pd.DataFrame(reform)
okc_buy_okcf_sell = data["okcf_bids"]-data["okc_asks"]
okc_sell_okcf_buy = data["okcf_asks"]-data["okc_bids"]
n = okc_buy_okcf_sell.shape[0]
plt.plot(okc_buy_okcf_sell,label = "okc_buy_okcf_sell")
plt.plot(okc_sell_okcf_buy,label = "okc_sell_okcf_buy")
plt.legend()
max_coin = 1
status = 0
now_coin = 0
for i in range(n):
    if okc_buy_okcf_sell[i]>600 and status == 0:
        money_f = data["okcf_bids"][i]*max_coin
        money = data["okc_asks"][i]*max_coin
        status = 1
    elif status == 1 and okc_sell_okcf_buy[i]<400:
        now_coin-=money / data["okc_bids"][i]
        now_coin += money_f/data["okcf_asks"][i]
        status = 0
print now_coin
# plt.plot([500 for i in range(okc_buy_okcf_sell.shape[0])])
plt.show()
# data = data.set_index('timestamp')
# # print data
# data["okc"] = data["okc"].map(lambda x:pd.Series(x))
# data["okcf"] = data["okcf"].map(lambda x:pd.Series(x))
# data["yunbi"] = data["yunbi"].map(lambda x:pd.Series(x))
print data
# print pd.Panel(data)
