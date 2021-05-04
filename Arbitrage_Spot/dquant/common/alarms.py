# -*- coding: utf-8 -*-

import threading
import time
import json
from dquant.common.sms_yuntongxun import sendTemplateSMS
from dquant.util import get_ip
from dquant.util import get_ip


#to_list = ['15011330375']
to_list = ['15210561008', '13071818809'] # yx, hq
#ALARM_TEMPLATE_ID = 228749
BAOCANG_TEMPLATE_ID = 230430

ERROR_TEMPLATE_ID = 234027
BLOCK_TEMPLATE_ID = 234028
TIMEOUT_TEMPLATE_ID = 239335

DEAD_SECONDS = 100
#DEAD_SECONDS = 10
MAX_ERROR = 10
#MAX_ERROR = 1

ALARM_ON_OFF = True

NAMES = {
    'Binance': 'bin',
    'Bitfinex': 'bfx',
    'OKEX': 'ok',
    'HuoBiPro': 'hb',
    "SpotDiff": 'maker2',
}


def deal_name(name_list):

    txt = ''
    for name in set(name_list):
        txt = '{}_{}'.format(NAMES[name], txt)
    return txt[:-1]


class BlockAlarm(threading.Thread):
    def __init__(self, q_hb, last_hb=int(time.time())):
        super(BlockAlarm, self).__init__()
        self.last_hb = last_hb
        self.last_platform = None
        self.q_hb = q_hb

    def run(self):
        '''记录上一次心跳的时间。如果100s没收到心跳，报警'''

        while True:

            if not ALARM_ON_OFF:
                break

            now = int(time.time())

            if now - self.last_hb >= DEAD_SECONDS and self.last_platform: # 超过100s没收到心跳
                for to in to_list:
                    sendTemplateSMS(to, [get_ip(), self.last_platform], BLOCK_TEMPLATE_ID)
                break

            if self.q_hb.qsize():
                msg = self.q_hb.get()
                self.last_hb = msg['hb'] # 记录上次心跳
                print('msg: ', msg)
                self.last_platform = NAMES[msg['name']]


class AlarmError(threading.Thread):
    def __init__(self, q_errors,):
        super(AlarmError, self).__init__()
        self.q_errors = q_errors
        self.msgs = []
        self.names = []

    def run(self):

        while True:
            if not ALARM_ON_OFF:
                break

            if len(self.msgs) >= 1000:
                self.msgs.clear()

            m = self.q_errors.get()
            self.msgs.append(m)

            if len(self.msgs) < MAX_ERROR: # 显然error不够
                continue

            if self.should_alarm():
                names = deal_name(self.names)
                for to in to_list:
                    sendTemplateSMS(to, [get_ip(), json.dumps(names)], ERROR_TEMPLATE_ID)
                break

    def should_alarm(self):
        '''判断是否需要告警:10s内10次error则报警
            需要：返回True。否则返回False
        '''

        times = sorted(self.msgs, key=lambda x: x['timestamp'])

        lens = len(times)
        max = 1
        cmp = times[0]['timestamp']
        tmp = 1
        self.names.append(times[0]['name'])

        for i in range(1, lens, 1):
            if times[i]['timestamp'] - cmp < 10000:
                tmp += 1
                self.names.append(times[i]['name'])
            else:
                # 重新开始算连续的5个
                cmp = times[i]['timestamp']
                tmp = 1
                self.names.clear()
                self.names.append(times[i]['name'])

            if tmp > max:
                max = tmp

            if max >= MAX_ERROR:
                print(self.msgs)
                return True

        return False


def alarm_of_stock(current_price, baoCang_price, ttype):

    print('alarm_of_stock args: ', current_price, baoCang_price, ttype)
    success = False
    if ttype == 'long':
        if (current_price - baoCang_price)/current_price <= 0.3:
            for to in to_list:
                sendTemplateSMS(to, ['{}.{}'.format(get_ip(), current_price), baoCang_price], BAOCANG_TEMPLATE_ID)
            success = True
    elif ttype == 'short':
        if (baoCang_price - current_price)/baoCang_price <= 0.3:
            for to in to_list:
                sendTemplateSMS(to, ['{}.{}'.format(get_ip(), current_price), baoCang_price], BAOCANG_TEMPLATE_ID)
            success = True

    return success


def timeout_alarm(ip, platform, api):
    '''
    【深浅科技】ip: {1}，平台：{2}，接口：{3}，超时了。
    '''

    if not ALARM_ON_OFF:
        return

    for to in to_list:
        sendTemplateSMS(to, [ip, platform, api], TIMEOUT_TEMPLATE_ID)


if __name__ == "__main__":
    timeout_alarm('1,2,3,4', 'bfx', 'cancel')