import bittrex
import OKCoin
import json
config = json.load(open("config_future.json",'r'))
okc = OKCoin.OKCoin(config,currency="btc_cny")
print okc.get_account()
# print round(0.0011,3)
# print okc.buy(round(0.0011,3),0.1)

# btx = bittrex.Bittrex(config)
# # print btx.get_currencies()
# # print json.dumps(btx.getDepth(),indent=4)
# print json.dumps(btx.get_account(tillOK=True),indent=4)
# print json.dumps(btx.getDepth(),indent=4)
# print json.dumps(btx.buy(amount = 0.1,rate = 0.01,tillOK=True),indent=4)
# # uuid = "5213e271-f8f1-48ea-afd3-8856a6d7796a"
# # uuid = "bb786a7a-26f4-43ab-84ca-d84793bba5ed"
# # uuid = "55e6e6df-6d21-4b65-9f2d-1b3ecd3046ae"
# uuid = "ed64fbc4-fb75-4fd4-a6cf-cb33a159ace8"
# # uuid = "8f97764c-4162-4c1b-acee-fe877e44517a"
# # print json.dumps(btx.getOrder(uuid=uuid,tillOK=True))
# # print json.dumps(btx.deleteOrder(uuid=uuid,tillOK=True))
# # print json.dumps(btx.deleteOrder(uuid=uuid),indent=4)