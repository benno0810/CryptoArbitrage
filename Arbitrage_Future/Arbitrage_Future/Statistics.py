import YunBi
import json
import HuoBi
import CNBTC
import numpy as np
import matplotlib.pyplot as plt
yb_period = 1
cnbtc_period = "1min"
config = json.load(open("config.json"))
cnbtc = CNBTC.CNBTC(config)
yb = YunBi.Yunbi(config,"LiChen")
hb = HuoBi.HuoBi(config)
# print hb.getK()
yb_list = yb.getK(period=yb_period,number=1000)
# yb_list[0][0]
print yb_list
print cnbtc
cnbtc_list = cnbtc.getK(period=cnbtc_period,since=yb_list[0][0]*1000)
print cnbtc_list
size = min(len(cnbtc_list["data"]),len(yb_list))
yb_list = np.asarray(yb_list)[:size,2:4]
cnbtc_list = np.asarray(cnbtc_list["data"])[:size,2:4]
yb_price = yb_list.mean(axis=1)
cnbtc_price = cnbtc_list.mean(axis=1)
# print yb_price,cnbtc_price
print yb_price-cnbtc_price
plt.hist(yb_price-cnbtc_price,100)
plt.show()