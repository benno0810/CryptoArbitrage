import collections
import logging
from configparser import ConfigParser
from pprint import pprint

import os

from dquant.constants import Constants
from dquant.util import Util

# logging.basicConfig(level=logging.INFO)
# print(__name__)
logger = logging.getLogger(__name__)

section_names = 'fortest', 'datadog', 'influxdb', 'okex', 'okex_future', 'bitmex', 'bitfinex', 'binance', 'mongo', 'huobi', 'redis', 'monitor', 'customized_precisions'


class MyConfiguration():
    __config_dict = collections.defaultdict(dict)

    def __init__(self, *file_names):
        parser = ConfigParser()
        parser.optionxform = str  # make option names case sensitive

        for file_name in file_names:
            found = parser.read(file_name)
            raw_file_name = result = file_name.split('/')[-1]
            group = Util.slice_till_dot(raw_file_name)

            if not found:
                raise ValueError('No config file found!')
            for name in section_names:
                self.__config_dict[group].update(parser.items(name))

    def pretty_print(self):
        pprint(self.__config_dict)

    def get_config_base(self, state, key):
        try:
            result = self.__config_dict[state][key]
            logger.info("key={}, result={}".format(key, result))

            return result
        except KeyError:
            logger.error(KeyError)

    def get_config(self, key):
        return self.get_config_base(os.environ.get(Constants.DQUANT_ENV), key)

    def get_int_config(self, key):
        return int(self.get_config(key))

    def get_float_config(self, key):
        return float(self.get_config(key))

    def get_bool_config(self, key):
        return self.get_config(key) == 'true' or self.get_config(key) == 'True'

    def get_precisions(self, name, symbol):
        # bitfinex_ethusdt_amount
        metas = ['min_amount', 'price', 'amount']
        return_list = []
        for meta in metas:
            cfg_name = "{}_{}_{}".format(name.lower(), symbol.lower(), meta)
            try:
                ret = None
                if meta == 'min_amount':
                    ret = self.get_float_config(cfg_name)
                else:
                    ret = self.get_int_config(cfg_name)
            except Exception:
                logger.error("Cannot find %s precision: %s %s, using default" % (meta, name.lower(), symbol.lower()))
            finally:
                return_list.append(ret)
        return return_list

cfg = MyConfiguration(os.path.join(os.path.dirname(__file__), '../config/dev.cfg'),
                      os.path.join(os.path.dirname(__file__), '../config/pro.cfg'))
