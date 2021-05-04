import os
import bisect
import numpy as np
check_start = '2017-06-08 08:00:00'
check_end = '2017-06-10 23:59:59'
extra_money = 0
extra_coin = 0
def float_list(l):
    l = l.strip()
    l = l.split(' ')[2:]
    return np.asarray([float(k) for k in l])
def float_list_tmp(l):
    l = l.strip()
    l = l.split(' ')[2:]
    l.extend(['0' for i in range(len(l),8)])
    return [float(k) for k in l]
big_list = []
price_list = []
dir = '.'+os.sep+'log'+os.sep
for dir,s,file_list in os.walk(dir):
    for file_name in file_list:
        if file_name.startswith("balance"):
            f = open(dir+file_name)
            result = f.readlines()
            if len(result)>1:
                result.pop(-1)
                big_list.extend(result)
        if file_name.startswith("historyPrice"):
            f = open(dir+file_name)
            result = f.readlines()
            if len(result)>1:
                result.pop(-1)
                price_list.extend(result)
big_list = sorted(big_list)
price_list = sorted(price_list)
start = bisect.bisect(big_list,check_start)
end = bisect.bisect(big_list,check_end)-1
start_price = bisect.bisect(price_list,check_start)
end_price = bisect.bisect(price_list,check_end)-1
price_list_arr = price_list[start_price:end_price+1]
# print price_list_arr
name_list = ["cnbtc","yunbi","huobi","total"]
cash_fee = [0.0]
if start>end:
    print "no data find"
else:
    print "trade %d times"%(len(big_list))
    print big_list[start]+big_list[end]
    # print price_list[start_price]
    # print price_list[end_price]
    average_start_price = float_list(price_list[start_price])
    average_end_price = float_list(price_list[end_price])
    average_end_price = average_end_price[:-2]
    print "start price %10f"%average_start_price.mean()
    print "end price   %10f"%average_end_price.mean()
    start_data_list = float_list(big_list[start])

    end_data_list = float_list(big_list[end])
    # print end_data_list
    diffCoin = end_data_list[-2]-start_data_list[-2]-extra_coin
    diffCash = end_data_list[-1]-start_data_list[-1]-extra_money
    for i in range(len(name_list)):
        print "%-10s coin_diff:%20f cash_diff:%20f"%(name_list[i],end_data_list[i*2]-start_data_list[i*2],end_data_list[i*2+1]-start_data_list[i*2+1])
    print "\ntotal diff coin asset: %15f\n"%(diffCoin*average_end_price.mean())
    print "total diff coin and cash asset:%16f\n"%(diffCoin*average_end_price.mean()+diffCash)

thres = np.asarray([[ 999999.,               5.13750278,       7.40391544,  7.40391544        ],
                    [5.13750278,  999999.,               7.40391544,   7.40391544        ],
                    [     9.51072065,      15.67712102,  999999.,          13.04212748        ],
                    [ 9.51072065,         7.4039154,          13.04212748,          999999.        ]])
price_arr = np.asarray([float_list_tmp(l) for l in price_list_arr])
# print price_arr.shape,len(price_list_arr)
times = np.zeros(thres.shape)
times_execute = np.zeros(thres.shape)
price_diff_list = []
print price_arr
money = 0
print price_arr
num = np.zeros(8)
for l in range(price_arr.shape[0]):
    max_diff = -5000
    id = (-1,-1)
    c = price_arr[l,:]
    num+=c>10
    for i in range(4):
        for j in range(4):
            price_diff = price_arr[l,j*2+1]-price_arr[l,i*2]

            if price_diff-thres[i,j]>max_diff:
                max_diff = price_diff-thres[i,j]
                id = (i,j)
            if price_diff>thres[i,j]:
                times[i,j]+=1
    price_diff_list.append(max_diff)
    if id[0]>=0 and max_diff>0:
        money+=max_diff*0.2
        times_execute[id[0],id[1]] +=1
print num
print times_execute
money_weight = times_execute.sum(axis = 0)/num[::2]
coin_weight = times_execute.sum(axis = 1)/num[1::2]
print money_weight/money_weight.sum()
print coin_weight/coin_weight.sum()
print times_execute
print times_execute.sum()
print times.sum()
print price_arr.shape[0]
print money
import matplotlib.pyplot as plt
plt.hist(price_diff_list,bins=100)
# plt.hist(price_arr[:,2]-price_arr[:,1])
plt.show()
