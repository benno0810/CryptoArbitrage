from threading import Thread
import threading
import logging
import asyncio
import time
import websockets, queue
from dquant.config import cfg
from dquant.constants import Constants
from dquant.markets.order_monitor import (OrderMonitor, MakerMonitor,
                                          CancelledOrderMonitor, OrderResultMonitor)
from dquant.common.sms_yuntongxun import sendTemplateSMS
from dquant.common.alarms import AlarmError, timeout_alarm
from dquant.util import get_ip


logger = logging.getLogger(__name__)


class Market(Thread):
    q_errors = queue.Queue()
    alarm_error = AlarmError(q_errors)
    alarm_error.setDaemon(True)
    alarm_error.start()

    def __init__(self, market_currency, base_currency, meta_code, fee_rate):
        Thread.__init__(self)
        self.daemon = True
        self.base_url = None
        self._name = None
        self.name = None
        self.market_currency = market_currency
        self.base_currency = base_currency
        self.meta_code = meta_code
        self.fee_rate = fee_rate
        self.update_flags = {"depth": False}
        self.methods = {}
        self.monitor = cfg.get_bool_config(Constants.MONITOR)
        self.isTaker = False
        self.q = queue.Queue()
        self.q_orders = queue.Queue() # 成交的订单(有side字段区分是来自taker还是maker)
        self.q_cancelled_orders = queue.Queue() # 取消的订单
        self.q_orders_result = queue.Queue()
        self.q_maker = queue.Queue() # 下的maker订单
        self.q_taker_order_result = queue.Queue() # 下的taker订单结果
        self.loop = None
        self.ip = get_ip()
        self.latency_ok = {
            'buy': True,
            'cancel': True,
            'depth': True
        }

        order_monitor = OrderMonitor(self.q_orders)
        order_monitor.setDaemon(True)
        order_monitor.start()

        cancelled_order_monitor = CancelledOrderMonitor(self.q_cancelled_orders)
        cancelled_order_monitor.setDaemon(True)
        cancelled_order_monitor.start()

        order_result_monitor = OrderResultMonitor(self.q_orders_result)
        order_result_monitor.setDaemon(True)
        order_result_monitor.start()

        maker_monitor = MakerMonitor(self.q_maker)
        maker_monitor.setDaemon(True)
        maker_monitor.start()

        self.last_latency_state = True

    @property
    def latency_good(self):
        if self.latency_ok['buy'] and self.latency_ok['cancel'] and self.latency_ok['depth']:
            self.last_latency_state = True
            return True
        else:
            if self.last_latency_state:
                timerThread = threading.Timer(interval=1800, function=self.reset_latency)
                timerThread.setDaemon(True)
                timerThread.start()
                self.last_latency_state = False
            return False

    def reset_latency(self):
        self.latency_ok = {
            'buy': True,
            'cancel': True,
            'depth': True
        }

    def compute_latency(self, s_time, api):
        max_time = {
            'buy': 10,
            'cancel': 20,
            'depth': 10
        }
        e_time = time.time()
        if e_time - s_time >= max_time[api]:
            self.latency_ok[api] = False
            # 看邮件报警
            #if api != 'depth':
            #    timeout_alarm(self.ip, self.name, api)
        else:
            self.latency_ok[api] = True

    def err_timestamp(self):
        return int(time.time()*1000)

    def error(self, err_msg):
        logger.error(err_msg)
        self.q_errors.put({'name':self.name, 'err_msg': err_msg, 'timestamp':self.err_timestamp()})

    # 将所有flag设置为false
    def unset_flags(self, flags):
        # for name in self.update_flags:
        #     self.update_flags[name] = True
        for name in flags:
            self.update_flags[name] = False

    # 逐个检查flag，只有全部为真时（全部更新完毕），返回True
    def check_flags(self, flags):
        status = True
        for name in flags:
            status = (status and (self.update_flags[name]))
        return status

    async def sub_channel(self):
        # sub depth
        pass

    # 保持连接
    async def keep_connect(self):
        reconnect_count = 1
        while True:
            try:
                logger.info('%s websocket trying to reconnect (%s)...' % (self.name, reconnect_count))
                if self.websocket == None:
                    try:
                        self.websocket = await websockets.connect(self.base_url, timeout=20)
                    except Exception as ex:
                        logger.debug('%s websocket keep_connect timeout' % self.name)
                        continue
                else:
                    if not self.websocket.open:
                        await self.websocket.close()
                        logger.info('%s websocket closed, reconnect' % self.name)
                        try:
                            # 尝试行的重连方式看能否解决
                            self.websocket = None
                            self.websocket = await asyncio.wait_for(websockets.connect(self.base_url, timeout=20), timeout=20, loop=self.loop)
                            logger.debug(type(self.websocket))
                            # self.websocket = await websockets.connect(self.base_url, timeout=20)
                        except Exception as ex:
                            logger.debug('%s websocket keep_connect timeout' % self.name)
                            continue
                    else:
                        logger.info('%s websocket connected' % self.name)
                        break
            except Exception as ex:
                logger.error("keep_connect: %s" % ex)
                # continue
            finally:
                reconnect_count += 1
                await asyncio.sleep(0.5)
        await self.sub_channel()

    # 获取ticker（买一卖一报价）
    def get_ticker(self):
        depth = self.getDepth()
        if not depth:
            return None
        res = {'ask': {'price': 0, 'amount': 0}, 'bid': {'price': 0, 'amount': 0}}
        if len(depth['asks']) > 0:
            res['ask'] = depth['asks'][0]
        if len(depth["bids"]) > 0:
            res['bid'] = depth['bids'][0]
        return res

    def update(self,update_flags):
        """
        all update must ends with barrier.
        :argument update_flags {"depth": True}
        :return:
        """
        pass

    def getDepth(self):
        pass

    async def long(self, price, amount):
        pass

    async def short(self, price, amount):
        pass

    async def closeLong(self, price, amount):
        pass

    async def closeShort(self, price, amount):
        pass
