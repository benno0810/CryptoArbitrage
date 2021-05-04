import queue, os, logging
import threading
from copy import copy

import time

from dquant.constants import Constants
from dquant.markets._okex_future_ws import OkexFutureWs
import asyncio




class OkexTickers(threading.Thread):
    def __init__(self, meta_code):
        super(OkexTickers,self).__init__()
        os.environ[Constants.DQUANT_ENV] = "dev"
        # starting with Python 3.6 and 3.5.3, it will be recommended to never pass the new_event_loop() explicitly.
        # new = asyncio.new_event_loop()
        self.new = asyncio.new_event_loop()
        asyncio.set_event_loop(self.new)
        self.okex = OkexFutureWs(meta_code, self.new)
        self.okex.start()
        self.q = queue.Queue()
        self.q_output = queue.Queue()
        # 仓位
        self.lastPosition = {'long': 0, 'short': 0}
        # 策略程序getorder频率很高，如果与上次getorder结果相同就不需要log了
        self.last_get_order_info={'long':{'ordid':None, 'amount_filled': None}, 'short':{'ordid':None, 'amount_filled': None}}
        self.order_type={1:'long', 2:'short', 3:'close_long', 4:'close_short'}

    # 返回最后一个买/卖/删除记录，因为getorder不会记录已经成交或者删除的订单信息,而已经执行的订单保存在getHist里（只保存最近10个）
    def get_latest_order(self, side):
        # 查询买卖订单
        hist = self.okex.getHist()
        temp_hist = copy(hist)
        # 从最近成交/成功删除的订单开始遍历
        latest_order_id, latest_order_details = temp_hist[side].popitem()
        return {'ordid':latest_order_id, 'details': latest_order_details}


    def my_getOrder(self):
        # 初始化返回结果
        initial_info = {'ordid': None, 'price': None, 'amount_filled': None, 'amount_orig': None}
        ret = {'long': initial_info, 'short': initial_info}
        active_order = self.okex.get_order()
        for order_id, order_details in active_order.items():
            amount_filled = order_details['deal_amount']
            amount_orig = order_details['amount']
            side = self.order_type[order_details['type']]
            price = order_details['price']
            ret[side] = {'ordid': order_id, 'price': price, 'amount_filled': amount_filled, 'amount_orig': amount_orig}
        return ret

    def run(self):
        while True:
            print('waiting for get')
            m = self.q.get()
            print(m)
            if m['type'] == 'Delete all active orders':
                active_orders = self.okex.get_order()
                if active_orders:
                    temp_orders = copy(active_orders)
                    for order in temp_orders:
                        self.okex.delete_order(order)

            elif m['type'] == 'New order':
                price = m['price']
                side = m['side']
                amount = m['amount']
                if side == 'long':
                    result = self.okex.long(amount=amount, price=price)
                else:
                    result = self.okex.short(amount=amount, price=price)
                order = self.okex.get_order(result['order_id'])
                self.q_output.put({'type': 'Order new', 'ordid': order['order_id'], 'amount': order['amount']})


            elif m['type'] == 'Get long and short orders':
                ret = self.my_getOrder()
                amount_filled = None
                for side, details in ret.items():
                        amount_filled = details['amount_filled']
                        amount_orig = details['amount_orig']
                        if amount_orig:
                            self.lastPosition[side] = amount_orig - amount_filled
                            # 控制输出，与上次相同的数据就不用输出了
                            last_id = self.last_get_order_info[side]['ordid']
                            last_amount_filled = self.last_get_order_info[side]['amount_filled']
                            if last_id != details['ordid'] or last_amount_filled != amount_filled:
                                self.last_get_order_info[side]['ordid'] = details['ordid']
                                self.last_get_order_info[side]['amount_filled'] = amount_filled
                                logging.info('GetOrder: id %s, filled: %s' % (details['ordid'], amount_filled))
                        else:
                            try:
                                latest_executed_order = self.get_latest_order(side=side)
                                amount_filled = latest_executed_order['details']['deal_amount']
                                amount_orig = latest_executed_order['details']['amount']
                                amount_remain = amount_orig - amount_filled
                                self.lastPosition[side] = amount_remain             # 正常情况下是0
                                logging.info('GetOrder: id %s, filled: %s' % (latest_executed_order['ordid'], amount_filled))
                            except Exception as ex:
                                logging.error('ex')

                ret['amount_filled'] = amount_filled
                self.q_output.put(ret)

            elif m['type'] == 'Delete and place new order':
                ret = self.my_getOrder()
                #   待下单信息
                side = m['side']
                amount = m['amount']
                price = m['price']
                # 待删除订单信息
                ordid = ret[side]['ordid']
                old_price = ret[side]['price']

                # 删除订单
                # 订单状态未完成（可以查到订单号）
                if ordid:
                    self.okex.delete_order(ordid)
                    result = self.okex.get_order(ordid)
                    amount_filled = result['deal_amount']
                    amount_orig = result['amount']
                    amount_remain = amount_orig-amount_filled
                    old_price = result['price']
                    logging.info('Delete: canceling order %s @%s, filled %s, last position: %s' % (ordid, old_price, amount_filled, self.lastPosition[side]))
                # 订单已完成
                else:
                    try:
                        latest_executed_order = self.get_latest_order(side=side)
                        amount_filled = latest_executed_order['details']['deal_amount']
                        amount_orig = latest_executed_order['details']['amount']
                        amount_remain = amount_orig - amount_filled
                        self.lastPosition[side] = amount_remain  # 正常情况下是0
                        logging.info('Delete: id %s has been filled before deleted, amount: %s ' % (latest_executed_order['ordid'], amount_filled))
                    except Exception as ex:
                        logging.error(ex)

                # 下单， 数量是删除订单时返回的
                amount = amount_remain if amount_remain else amount
                if side == 'long':
                    res = self.okex.long(amount=amount, price=price)
                else:
                    res = self.okex.short(amount=amount, price=price)
                order = self.okex.get_order(res['order_id'])
                self.q_output.put({'type': 'Delete and place new order', 'ordid': order['order_id'], 'price': order['price'], 'amount': order['amount']})


if __name__ == "__main__":
    amount = 1
    os.environ[Constants.DQUANT_ENV] = "dev"
    okex = OkexTickers('btc_usd_this_week')
    okex.start()
    time.sleep(5)

    # 取消所有未成交的订单
    okex.q.put({'type': 'Delete all active orders'})
    time.sleep(5)

    # 挂买一卖一
    book = okex.okex.getDepth()
    ticker_bp = book['bids'][0]['price']
    ticker_sp = book['asks'][0]['price']
    okex.q.put({'type': 'New order', 'price': ticker_bp, 'amount': amount, 'side': 'long'})
    m = okex.q_output.get()
    logging.info('New order: Long %s @%s, lastPosition: %s' % (amount, ticker_bp, okex.lastPosition['long']))
    okex.lastPosition['long'] = m['amount']
    okex.q.put({'type': 'New order', 'price': ticker_sp, 'amount': amount, 'side': 'short'})
    okex.q_output.get()
    logging.info('New order: Short %s @%s, lastPosition: %s' % (amount, ticker_sp, okex.lastPosition['short']))
    okex.lastPosition['short'] = m['amount']

    async def main():
        while True:
            m = await okex.okex.q_trigger.get()
            book = okex.okex.getDepth()
            ticker_bp = book['bids'][0]['price']
            ticker_sp = book['asks'][0]['price']
            # 获取当前订单信息
            okex.q.put({'type': 'Get long and short orders'})
            m = okex.q_output.get()
            my_bp = m['long']['price']       # 如果有价格,则单子还未成交,如果是None,说明之前的单子已经成交
            my_sp = m['short']['price']
            if not my_bp:                   # 之前的买单已经成交, 下新买单
                okex.q.put({'type': 'New order', 'price': ticker_bp, 'amount': amount, 'side': 'long'})
                logging.info('New order: Long %s @%s' % (amount, ticker_bp,))
                okex.q_output.get()
            elif ticker_bp > my_bp:         # 市场买一价格高于我的买价,撤销买单并重新挂单
                okex.q.put({'type': 'Delete and place new order', 'side': 'long', 'price': ticker_bp, 'amount': amount})
                logging.info('Delete and place new order: Long %s @%s, past: @%s' % (amount, ticker_bp, my_bp))
                okex.q_output.get()

            if not my_sp:                   # 之前的卖单已经成交, 下新卖单
                okex.q.put({'type': 'New order', 'price': ticker_sp, 'amount': amount, 'side': 'short'})
                logging.info('New order: Short %s @%s' % (amount, ticker_sp))
                okex.q_output.get()
            elif ticker_sp < my_sp:         # 市场卖一价格低于我的卖价,撤销卖单并重新挂单
                okex.q.put({'type': 'Delete and place new order', 'side': 'short', 'price': ticker_sp, 'amount': amount})
                logging.info('Delete and place new order: Short %s @%s, past: @%s' % (amount, ticker_sp, my_sp))
                okex.q_output.get()
            time.sleep(0.5)


    policy = asyncio.get_event_loop_policy()
    policy.set_event_loop(policy.new_event_loop())
    loop = asyncio.get_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
