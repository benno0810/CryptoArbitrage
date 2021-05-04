import OKCoinFuture
import json
config = json.load(open("config_future.json",'r'))
okcf = OKCoinFuture.OKCoinFuture(config)
print okcf.get_account()
print okcf.getDepth()
print okcf.get_position()
print okcf.exchange_rate()
t = [1]
print t[1:]
# print okcf.getOrder('20170929034L')
# print okcf.long(amount=22)
# print okcf.deleteOrder(orderId = str(7611105333L))
# print okcf.getOrder(orderId = 7611105333L)
#7611105333L
#7611137194L
#7611159788L