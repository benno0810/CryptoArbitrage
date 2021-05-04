import base64
import os
import random
import re
import socket
import time
import logging
import datetime


def get_ip():
    myname = socket.getfqdn(socket.gethostname())
    # 获取本机ip
    myaddr = socket.gethostbyname(myname)
    # myaddr = '127.0.0.1'
    return myaddr


class Util():

    @staticmethod
    def slice_till_dot(str):
        """
        :type string
        """
        slice_till_dot = re.compile(r"^(.*?)\..*")
        match_result = re.match(slice_till_dot, str)
        if match_result is not None:
            return match_result.group(1)
        else:
            return None

    @staticmethod
    def bfx_get_gid(strategy_id):
        """
        :type string
        """
        ip_id = ''
        myaddr = get_ip()
        myaddr_list = myaddr.split('.')

        ip_id += str(myaddr_list[-2]).zfill(3) + str(myaddr_list[-1]).zfill(3)
        # for num in myaddr_list:
        #     ip_id += str(num).zfill(3)
        pid = str(os.getpid()).zfill(5)
        strategy_id = str(strategy_id).zfill(2)

        #return int(ip_id+strategy_id+pid)
        return {'gid': int(ip_id+strategy_id+pid), 'ip': ip_id, 'strategy_id': strategy_id, 'pid': 1}

    @staticmethod
    def bfx_from_gid(gid):
        """
        :type string
        :return: length max 12
        """
        #  从后向前解析

        ip = gid[:3]
        strategy_id = int(gid[3:5])
        pid = int(gid[5:])

        return ip, strategy_id, pid

    @staticmethod
    def bfx_get_cid():
        '''
        :return: length max 13
        '''
        pid = str(os.getpid()).zfill(5)
        ts = str(int(time.time() * 1000))[-8:]
        # ts = str(int(time.time()*1000))[-10:-2] + '0'
        return int(ts + pid)

    @staticmethod
    def bnc_get_cid(strategy_id):
        '''
        :return: length max 13
        '''
        myaddr = get_ip()
        myaddr_list = myaddr.split('.')
        new_addr = ''
        for i in myaddr_list:
            new_addr += i + '_'
        pid = str(os.getpid())
        r = str(random.randint(1, 10000))
        ts = str(int(time.time() * 1000))[-4:]
        message = '{}{}_{}_{}'.format(new_addr, str(strategy_id), pid, r + ts)
        return message

    @staticmethod
    def bnc_from_cid(cid):
        '''
        :return: length max 13
        '''
        try:
            l = cid.split('_')
            ip = '{}.{}.{}.{}'.format(l[0], l[1],l[2],l[3])
            strategy_id = l[4]
            pid = l[5]
            return {'ip': ip, 'strategy_id': strategy_id, 'pid': pid}
        except:
            pass

    @staticmethod
    def bnc_pid_from_cid(cid):
        '''
        :return: length max 13
        '''
        try:
            l = cid.split('_')  # cid= 'xxx'.  l就是list。里面只有1个元素，因为cid没有 '_'
            pid = l[5]  # 越界 。跑到except去
            return pid
        except:
            pass

    @staticmethod
    def build_order_result(status, order_id=None, side='', trade_pair='', price=0, amount_filled=None,
                           amount_filled_this_time=None, amount_orig=None, amount_remain=None,
                           time_stamp=int(time.time()*1000), client_order_id=None,
                           error_message='', platform_id='', **kwargs):
        try:
            if status:
                if amount_orig is not None:
                    amount_orig = abs(float(amount_orig))
                    price = abs(float(price))
                    if amount_filled is None:
                        amount_remain = abs(float(amount_remain))
                        amount_filled = amount_orig - amount_remain
                    if amount_remain is None:
                        amount_filled = abs(float(amount_filled))
                        amount_remain = amount_orig - amount_filled

            ret = {'status':status, 'order_id':order_id, 'side':side, 'trade_pair': trade_pair, 'price':price,
                'amount_filled':amount_filled, 'amount_filled_this_time':amount_filled_this_time, 'amount_orig':amount_orig,
                'amount_remain':amount_remain, 'time_stamp':time_stamp, 'client_order_id':client_order_id,
                "error_message": error_message, 'platform_id': platform_id}
            ret.update(kwargs)
            return ret
        except Exception as ex:
            logging.error('build_order_result: %s' % ex)

    @staticmethod
    def build_order_store(order_id=None, side=None, trade_pair=None, price=None, amount_filled=None, time_stamp=int(time.time()*1000),
        client_order_id=None, platform_name=None, platform_account_id=None,strategy_id=None, fee_rate=0.001, fee='0_usdt', **kwargs):
        '''

        :param order_id:
        :param side: sell; buy
        :param trade_pair:
        :param price:
        :param amount_filled:
        :param time_stamp:
        :param client_order_id:
        :param platform_name:
        :param platform_account_id:
        :param strategy_id:
        :param kwargs:
        :return:
        '''
        try:
            ip = get_ip()
            pid = os.getpid()
            platform_id_field = '{}_id'.format(platform_name)
            order_data = {'order_id': order_id, 'side': side, 'trade_pair': trade_pair, 'price': price, 'fee': fee,
                'amount_filled': amount_filled, 'order_time': time_stamp, 'account_id': client_order_id,
                'platform_id': platform_name,'strategy_id': strategy_id,  platform_id_field: platform_account_id}
            # order_data.update({"_id": datetime.datetime.utcnow(), 'timestamp': int(time.time() * 1000), 'ip': ip, 'pid':pid})
            # 2018.3.5 更新：为避免_id冲突，使用默认_id
            order_data.update({'timestamp': int(time.time() * 1000), 'ip': ip, 'pid': pid})
            return order_data
        except Exception as e:
            print('build_order_store error: {}'.format(e))


if __name__ == '__main__':
    print(Util.bnc_pid_from_cid('192_168_79_1_0_9012_69994923'))
    #print(Util.bnc_get_cid(1))
    #print(Util.bfx_get_gid(1))
    #print(Util.bfx_get_cid())
