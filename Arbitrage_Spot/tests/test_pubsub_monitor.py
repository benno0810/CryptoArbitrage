import json
import unittest

import os

from dquant.constants import Constants
from dquant.pipeline.monitor_subscriber import monitorSubscriber
from dquant.pipeline.publisher import Publisher


class ConfigTestSuite(unittest.TestCase):
    """for config test case"""

    @classmethod
    def setUpClass(cls):
        os.environ[Constants.DQUANT_ENV] = "dev"

    def test_json_dump(self):
        print(json.dumps({'symbol': 'eth',
                          'exchange': 'okex',
                          'price': '2999.31'}))

    def test_get_config(self):
        print(os.environ[Constants.DQUANT_ENV])
        sub = monitorSubscriber(['price'])
        sub.start()
        publisher = Publisher()
        publisher.publish_price({'symbol': 'eth',
                                 'exchange': 'okex',
                                 'price': '2999.31'})
        # publisher = Publisher()
        # publisher.redis.publish('price',"simple message")


if __name__ == '__main__':
    unittest.main()
