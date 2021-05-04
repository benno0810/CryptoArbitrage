import json

import redis

from dquant.config import cfg
from dquant.constants import Constants


class Publisher():
    def __init__(self):
        self.host = cfg.get_config(Constants.REDIS_HOST)
        self.port = cfg.get_config(Constants.REDIS_PORT)
        self.redis = redis.Redis(host=self.host, port=self.port)

    def publish_price(self,data):
        '''
        data should be json encodes
        :return:
        '''
        self.redis.publish('price',json.dumps(data))


