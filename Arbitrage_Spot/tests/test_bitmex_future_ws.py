import unittest
import time
import asyncio
import os

from dquant.constants import Constants
from dquant.markets._bitmex_future_ws import BitmexFutureWs


class BitmexFutureTestSuite(unittest.TestCase):
    """for config test case"""

    @classmethod
    def setUpClass(cls):
        os.environ[Constants.DQUANT_ENV] = "dev"
        loop = asyncio.get_event_loop()
        cls.ex = BitmexFutureWs("btc_usd", loop)
        cls.ex.start()
        time.sleep(15)

    #@unittest.skip("skipping long")
    def test_b_long(self):
        '''
        :return: {'orderID': 'd4e91f38-514e-d4cb-89df-9cf95266f693', 'clOrdID': '', 'clOrdLinkID': '', 'account': 122138, 'symbol': 'XBTUSD', 'side': 'Sell', 'simpleOrderQty': None, 'orderQty': 1, 'price': 10771.5, 'displayQty': None, 'stopPx': None, 'pegOffsetValue': None, 'pegPriceType': '', 'currency': 'USD', 'settlCurrency': 'XBt', 'ordType': 'Limit', 'timeInForce': 'GoodTillCancel', 'execInst': '', 'contingencyType': '', 'exDestination': 'XBME', 'ordStatus': 'New', 'triggered': '', 'workingIndicator': True, 'ordRejReason': '', 'simpleLeavesQty': 0.0001, 'leavesQty': 1, 'simpleCumQty': 0, 'cumQty': 0, 'avgPx': None, 'multiLegReportingType': 'SingleSecurity', 'text': 'Submitted via API.', 'transactTime': '2017-11-29T10:02:03.591Z', 'timestamp': '2017-11-29T10:02:03.591Z'}
        '''
        result = self.ex.long(amount=1, lever=2)
        print('long结果：', result)

    #@unittest.skip("skipping short")
    def test_c_short(self):
        '''
        :return: {'orderID': 'd4e91f38-514e-d4cb-89df-9cf95266f693', 'clOrdID': '', 'clOrdLinkID': '', 'account': 122138, 'symbol': 'XBTUSD', 'side': 'Sell', 'simpleOrderQty': None, 'orderQty': 1, 'price': 10771.5, 'displayQty': None, 'stopPx': None, 'pegOffsetValue': None, 'pegPriceType': '', 'currency': 'USD', 'settlCurrency': 'XBt', 'ordType': 'Limit', 'timeInForce': 'GoodTillCancel', 'execInst': '', 'contingencyType': '', 'exDestination': 'XBME', 'ordStatus': 'New', 'triggered': '', 'workingIndicator': True, 'ordRejReason': '', 'simpleLeavesQty': 0.0001, 'leavesQty': 1, 'simpleCumQty': 0, 'cumQty': 0, 'avgPx': None, 'multiLegReportingType': 'SingleSecurity', 'text': 'Submitted via API.', 'transactTime': '2017-11-29T10:02:03.591Z', 'timestamp': '2017-11-29T10:02:03.591Z'}
        '''
        result = self.ex.short(amount=1)
        print('short结果: ', result)

    #@unittest.skip("skipping close short")
    def test_d_close_short(self):
        result = self.ex.closeShort(amount=1)
        print('close short: ', result)

    #@unittest.skip("skipping close long")
    def test_e_close_long(self):
        result = self.ex.closeLong(price=-1, amount=1)
        print('close long: ', result)

    #@unittest.skip("skipping get order")
    def test_f_get_order(self):
        '''
        :return: [{'orderID': '295b6c50-74bd-1444-4905-9259d9d04903', 'clOrdID': '', 'clOrdLinkID': '', 'account': 122138, 'symbol': 'XBTUSD', 'side': 'Buy', 'simpleOrderQty': None, 'orderQty': 1, 'price': 10564.5, 'displayQty': None, 'stopPx': None, 'pegOffsetValue': None, 'pegPriceType': '', 'currency': 'USD', 'settlCurrency': 'XBt', 'ordType': 'Market', 'timeInForce': 'ImmediateOrCancel', 'execInst': '', 'contingencyType': '', 'exDestination': 'XBME', 'ordStatus': 'Filled', 'triggered': '', 'workingIndicator': False, 'ordRejReason': '', 'simpleLeavesQty': 0, 'leavesQty': 0, 'simpleCumQty': 9.466e-05, 'cumQty': 1, 'avgPx': 10564, 'multiLegReportingType': 'SingleSecurity', 'text': 'Submitted via API.', 'transactTime': '2017-11-29T07:54:28.425Z', 'timestamp': '2017-11-29T07:54:28.425Z'}]
        '''
        res = self.ex.getOrder('517e62a5-2abf-f780-d15b-9a32d10beaa9')
        print('get short order: ', res)

    @unittest.skip("skipping delete order")
    def test_g_delete_order(self):
        '''
        :return: [{'orderID': 'd4e91f38-514e-d4cb-89df-9cf95266f693', 'clOrdID': '', 'clOrdLinkID': '', 'account': 122138, 'symbol': 'XBTUSD', 'side': 'Sell', 'simpleOrderQty': None, 'orderQty': 1, 'price': 10771.5, 'displayQty': None, 'stopPx': None, 'pegOffsetValue': None, 'pegPriceType': '', 'currency': 'USD', 'settlCurrency': 'XBt', 'ordType': 'Limit', 'timeInForce': 'GoodTillCancel', 'execInst': '', 'contingencyType': '', 'exDestination': 'XBME', 'ordStatus': 'Filled', 'triggered': '', 'workingIndicator': False, 'ordRejReason': '', 'simpleLeavesQty': 0, 'leavesQty': 0, 'simpleCumQty': 9.284e-05, 'cumQty': 1, 'avgPx': 10771, 'multiLegReportingType': 'SingleSecurity', 'text': 'Submitted via API.', 'transactTime': '2017-11-29T10:02:03.591Z', 'timestamp': '2017-11-29T10:03:01.806Z', 'error': 'Unable to cancel order due to existing state: Filled'}]
        '''
        result = self.ex.deleteOrder('517e62a5-2abf-f780-d15b-9a32d10beaa9')
        print('delete short order: ', result)

    def test_h_get_ticker(self):

        result = self.ex.get_ticker()
        print('get ticker: {}'.format(result))

    def test_i_get_trade(self):
        result = self.ex.get_trade()
        print('get trade: {}'.format(result))

    def test_j_get_account(self):
        result = self.ex.get_account()
        print('get account: {}'.format(result))

    #@unittest.skip("skipping get depth")
    def test_k_get_depth(self):
        print('盘口数据', self.ex.getDepth())

if __name__ == '__main__':
    unittest.main()