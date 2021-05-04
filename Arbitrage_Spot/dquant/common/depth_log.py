# -*- coding: utf8 -*-

import sys
sys.path.append('.')
sys.path.append('../')
sys.path.append('../../')
import os

import logging
import time
from logging.handlers import TimedRotatingFileHandler
from dquant.constants import Constants
from dquant.config import cfg
from dquant import log_path

when = 'D'
backupCount = 14


def init_roll_log(log_file='roll.log', log_level=logging.DEBUG):
    '''
    按日期切分日志，过期则删

    :param log_file: log文件名
    :param log_level: log日志级别
    :return:
    '''

    good_log_path = '{}{}/'.format(log_path.split('dquant')[0], 'dquant/logs')

    print(good_log_path, log_file)

    TimeRthandler = TimedRotatingFileHandler(filename=good_log_path+log_file, when=when, backupCount=backupCount)
    formatter = logging.Formatter('%(asctime)s %(filename)s:%(lineno)d <%(thread)d> %(levelname)-8s %(message)s')
    TimeRthandler.setFormatter(formatter)
    log_obj = logging.getLogger('depth.roll.svr')
    log_obj.addHandler(TimeRthandler)
    log_obj.setLevel(log_level)
    return log_obj


if __name__ == '__main__':
    os.environ[Constants.DQUANT_ENV] = "dev"

    logger = init_roll_log('roll.log')
    logger.error('test error')
    logger.info('test_info')
    i = 0
    while True:
        logger.debug("test log roll %d", i)
        logger.info('test_info')
        i += 1
        time.sleep(2)