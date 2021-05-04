import unittest
import os
import logging
import sys

sys.path.append('../')
sys.path.append('../../')

from dquant.config import cfg
from dquant.constants import Constants



class ConfigTestSuite(unittest.TestCase):
    """for config test case"""

    @classmethod
    def setUpClass(cls):
        os.environ[Constants.DQUANT_ENV] = "dev"

    @unittest.skip("only for debug")
    def test_config_parse(self):
        val = cfg
        val.pretty_print()
        assert True

    @unittest.skip("only for debug")
    def test_get_config(self):
        val = cfg.get_config("test")
        self.assertTrue(val == "dev")

    @unittest.skip("only for debug")
    def test_get_redis(self):
        host = cfg.get_config(Constants.REDIS_PORT)
        port = cfg.get_config(Constants.REDIS_HOST)
        print(host + port)

    # @unittest.skip("only for debug")
    def test_log(self):
        logger = logging.getLogger('spam_application')
        logger.setLevel(logging.DEBUG)
        # create file handler which logs even debug messages
        fh = logging.FileHandler('spam.log')
        fh.setLevel(logging.DEBUG)
        # create console handler with a higher log level
        ch = logging.StreamHandler()
        ch.setLevel(logging.ERROR)
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        # add the handlers to the logger
        logger.addHandler(fh)
        logger.addHandler(ch)

        logging.debug('123ell')
        logging.info('hello')

if __name__ == '__main__':
    unittest.main()
