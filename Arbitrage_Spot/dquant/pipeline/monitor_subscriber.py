import json

import redis
import threading

from dquant.config import cfg
from dquant.constants import Constants


class monitorSubscriber(threading.Thread):
    def __init__(self, channels):
        threading.Thread.__init__(self)
        self.host = cfg.get_config(Constants.REDIS_HOST)
        self.port = cfg.get_config(Constants.REDIS_PORT)
        self.redis = redis.Redis(host=self.host, port=self.port)
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(channels)
        self.methods = {'price' : self.price_handler}

    def dispatcher(self, item):
        channel = item['channel'].decode("utf-8")
        rawdata = item['data']
        if not isinstance(rawdata, int):
            data = json.loads(rawdata.decode("utf-8"))
            print(channel + ":" + json.dumps(data))
            self.methods[channel](data)

    def price_handler(self, data):
        print("In price handler")
        print("do whatever with data")

    def run(self):
        for item in self.pubsub.listen():
            print(item)
            self.dispatcher(item)
