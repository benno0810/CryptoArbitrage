import OKCoin
import OKCoinFuture
import YunBi
import json
import threading
import Queue
import numpy
import time


def statis(a):
    print "number: %d mean: %f max: %f min: %f std : %f" % (a.shape[0], a.mean(), a.max(), a.min(), a.std())


numpy.set_printoptions(suppress=True)
history = open("log/historyPrice_%s.txt" % time.strftime('%Y_%m_%d_%H_%M_%S', time.localtime(time.time())), "a")
balance = open("log/balance%s.txt" % time.strftime('%Y_%m_%d %H_%M_%S', time.localtime(time.time())), 'a')
statuses = open("log/statuses.txt", 'a')
config = json.load(open("config_future.json", 'r'))

platform_list = {
    "current": {
        "OKCoin": OKCoin.OKCoinPlatform(config, "OKCoin")
        #"YunBi": YunBi.YunBiPlatform(config, "YunBi")
    },
    "future": {
        "OKCoinFuture": OKCoinFuture.OKCoinFuturePlatform(config, "OKCoinFuture")
    }
}

maxTransLimitation = int(config["MaxCoinTradeLimitation"])
tick = 0
btc_cny = ("BTC", "CNY")
btc_usd = ("BTC", "USD")
exchange_rate = platform_list["future"]["OKCoinFuture"].trade_accounts["OKCoinFuture"][btc_usd]["obj"].exchange_rate()
print exchange_rate
# status: 0:no long no short
# status: 1: long
# status: -1: short
status_json = json.load(open("status.json", "r"))
status = int(status_json["status"])
if status == 0:
    status_json["current_future"] = []
maxPosition = 20
gap = 10
current_sell_future_buy_thres = 1100
current_buy_future_sell_thres = 1100
close_current_sell_future_buy_thres = 600
close_current_buy_future_sell_thres = 600
current_sell_future_buy_diff = numpy.asarray([])
current_buy_future_sell_diff = numpy.asarray([])
money = 0
while True:
    time.sleep(2)
    tick += 1
    print "tick ", tick, " exchange rate ", exchange_rate
    for pltform_name, pltform in platform_list["current"].items():
        pltform.updateBalancePut()
        pltform.updateDepth({"BTC": 100 * maxTransLimitation / 4000.0})
        pltform.updateBalanceGet()
    for pltform_name, pltform in platform_list["future"].items():
        pltform.updateBalancePut()
        pltform.updateDepth({"BTC": 100 * maxTransLimitation / 4000.0})
        pltform.updateBalanceGet()
    if status <= 0 and status > -maxPosition:
        for key in platform_list["current"]["OKCoin"].trade_accounts.keys():
            print platform_list["current"]["OKCoin"].trade_accounts
            if platform_list["current"]["OKCoin"].accounts[key]["balances"]["CNY"]>maxTransLimitation*100.0*exchange_rate*2:
                current_obj = platform_list["current"]["OKCoin"].trade_accounts[key][btc_cny]
                break
        future_obj = platform_list["future"]["OKCoinFuture"].trade_accounts["OKCoinFuture"][btc_usd]
        print "diff %f %f" % (future_obj["sell_price"] * exchange_rate - current_obj["buy_price"],
                              current_obj["sell_price"] - future_obj["buy_price"] * exchange_rate)

        if (future_obj["sell_price"] * exchange_rate - current_obj["buy_price"]) > current_buy_future_sell_thres + abs(
                status) * gap:
            current_obj["trade_account_input_queue"].put(("buy", maxTransLimitation*100.0*exchange_rate/current_obj["buy_price"],current_obj["buy_price"], -1))
            future_obj["trade_account_input_queue"].put(("short", maxTransLimitation,future_obj["sell_price"], -1))
            coin_remain_c,current_money = current_obj["trade_account_output_queue"].get()
            coin_remain_f, future_money = future_obj["trade_account_output_queue"].get()

            #coin_remain_f = 0
            #coin_remain_c = 0
            #current_money = -maxTransLimitation * 100.0 * exchange_rate
            #future_money = maxTransLimitation * 100
            print ("current coin remain : %f, current_money : %f", coin_remain_c, current_money)
            print ("future coin remain : %f, future_money : %f", coin_remain_f, future_money)
            status += -1
            status_tmp = {
                "current": {
                    "platform_name": "OKCoin",
                    "account_name": "OKCoin",
                    "type": "long",
                    "money": abs(current_money),
                    "amount": round(maxTransLimitation * 100.0 * exchange_rate / current_obj["buy_price"], 3),
                    "coin_remain_c": coin_remain_c,
                    "current_money": current_money
                },
                "future": {
                    "platform_name": "OKCoinFuture",
                    "account_name": "OKCoinFuture",
                    "type": "short",
                    "amount": maxTransLimitation,
                    "coin_remain_f": coin_remain_f,
                    "future_money": future_money
                }
            }
            money += future_money * exchange_rate + current_money
            status_json["current_future"].append(status_tmp)
            status_json["status"] = status
            status_json["time"] = time.strftime('%Y_%m_%d_%H_%M_%S', time.localtime(time.time()))
            print status_json
            fp = open("status.json", "w")
            json.dump(status_json,fp, indent=4)
            fp.flush()
            json.dump(status_json, statuses, indent=4)
    if status >= 0 and status < maxPosition:
        future_obj = platform_list["future"]["OKCoinFuture"].trade_accounts["OKCoinFuture"][btc_usd]
        for key in platform_list["current"]["OKCoin"].trade_accounts.keys():
            if platform_list["current"]["OKCoin"].accounts[key]["balances"]["BTC"]>round(maxTransLimitation*100.0/future_obj["buy_price"],3)*2:
                current_obj = platform_list["current"]["OKCoin"].trade_accounts[key][btc_cny]
                break
        print "diff %f %f" % (future_obj["sell_price"] * exchange_rate - current_obj["buy_price"],
                              current_obj["sell_price"] - future_obj["buy_price"] * exchange_rate)
        if (current_obj["sell_price"] - future_obj[
            "buy_price"] * exchange_rate) > current_sell_future_buy_thres + status * gap:
            status += 1

            current_obj["trade_account_input_queue"].put(("sell", round(maxTransLimitation*100.0/future_obj["buy_price"],3),current_obj["sell_price"], -1))
            future_obj["trade_account_input_queue"].put(("long", maxTransLimitation,future_obj["buy_price"], -1))
            coin_remain_c,current_money = current_obj["trade_account_output_queue"].get()
            coin_remain_f, future_money = future_obj["trade_account_output_queue"].get()
            #coin_remain_f = 0
            #coin_remain_c = 0
            #current_money = round(maxTransLimitation * 100.0 / future_obj["buy_price"], 3) * current_obj["sell_price"]
            #future_money = -maxTransLimitation * 100
            print ("current coin remain : %f, current_money : %f",coin_remain_c,current_money)
            print ("future coin remain : %f, future_money : %f",coin_remain_f,future_money)
            status_tmp = {
                "current": {
                    "platform_name": "OKCoin",
                    "account_name": "OKCoin",
                    "type": "short",
                    "money": abs(current_money),
                    "amount": round(maxTransLimitation * 100.0 / future_obj["buy_price"], 3),
                    "coin_remain_c": coin_remain_c,
                    "current_money": current_money

                },
                "future": {
                    "platform_name": "OKCoinFuture",
                    "account_name": "OKCoinFuture",
                    "type": "long",
                    "amount": maxTransLimitation,
                    "coin_remain_f": coin_remain_f,
                    "future_money": future_money
                }
            }

            money += current_money + future_money * exchange_rate
            status_json["current_future"].append(status_tmp)
            status_json["status"] = status
            status_json["time"] = time.strftime('%Y_%m_%d_%H_%M_%S', time.localtime(time.time()))
            fp = open("status.json", "w")
            json.dump(status_json,fp, indent=4)
            fp.flush()
            json.dump(status_json, statuses, indent=4)
    if status < 0:
        current_platform_name = status_json["current_future"][0]["current"]["platform_name"]
        future_platform_name = status_json["current_future"][0]["future"]["platform_name"]
        current_account_name = status_json["current_future"][0]["current"]["account_name"]
        future_account_name = status_json["current_future"][0]["future"]["account_name"]
        for key in platform_list["current"]["OKCoin"].trade_accounts.keys():
            if platform_list["current"][current_platform_name].accounts[key]["balances"]["BTC"]>round(status_json["current_future"][0]["current"]["money"] / platform_list["current"][current_platform_name].trade_accounts[current_account_name][btc_cny]["sell_price"], 3)*2:
                current_account_name = key
                break
        current_obj = platform_list["current"][current_platform_name].trade_accounts[current_account_name][btc_cny]
        future_obj = platform_list["future"][future_platform_name].trade_accounts[future_account_name][btc_usd]
        if (future_obj["buy_price"] * exchange_rate - current_obj["sell_price"]) < close_current_buy_future_sell_thres:
            status += 1
            sell_amount = round(status_json["current_future"][0]["current"]["money"] / current_obj["sell_price"], 3)
            if sell_amount < 0.01:
                sell_amount = 0.01
            current_obj["trade_account_input_queue"].put(("sell", sell_amount,current_obj["sell_price"], -1))
            future_obj["trade_account_input_queue"].put(("close_short", maxTransLimitation,future_obj["buy_price"], -1))


            coin_remain_c,current_money = current_obj["trade_account_output_queue"].get()
            coin_remain_f, future_money = future_obj["trade_account_output_queue"].get()
            #coin_remain_f = 0
            #coin_remain_c = 0
            #current_money = current_obj["sell_price"] * sell_amount
            #future_money = -maxTransLimitation * 100
            print ("current coin remain : %f, current_money : %f", coin_remain_c, coin_remain_f)
            print ("future coin remain : %f, future_money : %f", coin_remain_c, coin_remain_f)
            status_json["current_future"] = status_json["current_future"][1:]
            status_json["status"] = status
            money += future_money * exchange_rate + current_money
            status_json["time"] = time.strftime('%Y_%m_%d_%H_%M_%S', time.localtime(time.time()))
            fp = open("status.json", "w")
            json.dump(status_json,fp, indent=4)
            fp.flush()
            json.dump(status_json, statuses, indent=4)
    if status > 0:
        current_platform_name = status_json["current_future"][0]["current"]["platform_name"]
        future_platform_name = status_json["current_future"][0]["future"]["platform_name"]
        current_account_name = status_json["current_future"][0]["current"]["account_name"]
        future_account_name = status_json["current_future"][0]["future"]["account_name"]
        future_obj = platform_list["future"][future_platform_name].trade_accounts[future_account_name][btc_usd]
        for key in platform_list["current"]["OKCoin"].trade_accounts.keys():
            if platform_list["current"][current_platform_name].accounts[key]["balances"]["CNY"]>round(maxTransLimitation*100.0/future_obj["sell_price"]*platform_list["current"][current_platform_name].trade_accounts[current_account_name][btc_cny]["buy_price"],3)*2:
                current_account_name = key
                break
        current_obj = platform_list["current"][current_platform_name].trade_accounts[current_account_name][btc_cny]
        if (current_obj["buy_price"] - future_obj["sell_price"] * exchange_rate) < close_current_sell_future_buy_thres:
            status -= 1
            current_obj["trade_account_input_queue"].put(("buy", round(maxTransLimitation*100.0/future_obj["sell_price"],3),current_obj["buy_price"], -1))
            future_obj["trade_account_input_queue"].put(("close_long", maxTransLimitation,future_obj["sell_price"], -1))


            coin_remain_c,current_money = current_obj["trade_account_output_queue"].get()
            coin_remain_f, future_money = future_obj["trade_account_output_queue"].get()
            #coin_remain_f = 0
            #coin_remain_c = 0
            #current_money = -current_obj["buy_price"] * maxCoinLimitation
            #future_money = future_obj["sell_price"] * maxCoinLimitation
            status_json["current_future"] = status_json["current_future"][1:]
            status_json["status"] = status
            money -= current_money + future_money * exchange_rate
            # money-=current_obj["buy_price"] - future_obj["sell_price"]*exchange_rate
            status_json["time"] = time.strftime('%Y_%m_%d_%H_%M_%S', time.localtime(time.time()))
            fp = open("status.json", "w")
            json.dump(status_json,fp, indent=4)
            fp.flush()
            json.dump(status_json, statuses, indent=4)

    current_buy_future_sell_diff = numpy.append(current_buy_future_sell_diff,
                                                (future_obj["sell_price"] * exchange_rate - current_obj["buy_price"]))
    current_sell_future_buy_diff = numpy.append(current_sell_future_buy_diff,
                                                (current_obj["sell_price"] - future_obj["buy_price"] * exchange_rate))
    if current_sell_future_buy_diff.shape[0] > 10000:
        current_sell_future_buy_diff = current_sell_future_buy_diff[-10000:]
    if current_buy_future_sell_diff.shape[0] > 10000:
        current_buy_future_sell_diff = current_buy_future_sell_diff[-10000:]
    statis(current_buy_future_sell_diff)
    statis(current_sell_future_buy_diff)
    print status_json["status"]
    #print json.dumps(status_json, indent=4)
    time.sleep(1)
    print "money", money
    print "\n"
