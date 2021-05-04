# -*- coding: utf-8 -*-
import sys

sys.path.append('.')
sys.path.append('../')
sys.path.append('../../')

from pymongo import MongoClient
from dquant.constants import Constants

# mongo_port = 27017
# mongo_address = 'localhost'
# username = None
# password = None
from dquant.config import cfg


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class MongoConnOrder(metaclass=Singleton):
    def __init__(self):
        mongo_address = cfg.get_config(Constants.MONGO_IP)
        mongo_port = cfg.get_int_config(Constants.MONGO_PORT)
        username = cfg.get_config(Constants.MONGO_USER)
        password = cfg.get_config(Constants.MONGO_PWD)
        self.client = MongoClient(mongo_address, mongo_port, username=username, password=password, minPoolSize=10, authMechanism='SCRAM-SHA-1')
        #self.client = MongoClient(mongo_address, mongo_port, username=username, password=password, minPoolSize=10, authMechanism='MONGODB-CR')
        #self.client = MongoClient('127.0.0.1', 27017, minPoolSize=10)


class MongoConnTrade(metaclass=Singleton):
    '''
        trade存储在TickerPicker里。由zhouyang负责
    '''
    def __init__(self):
        mongo_address = '52.199.28.152'
        mongo_port = 27017
        username = 'admin'
        password = 'VxaR3QPbdpxPNFfiVsxWCKRx'
        #username = 'root'
        #password = 'Zcytl123!'
        self.client = MongoClient(mongo_address, mongo_port, username=username, password=password, minPoolSize=10)


class MongoConn():

    def __init__(self, ip='127.0.0.1', port=27017, username='', password=''):
        if username and password:
            self.client = MongoClient(ip, port, username=username, password=password)
        else:
            self.client = MongoClient(ip, port)

