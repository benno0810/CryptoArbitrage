from dquant.constants import Constants
from dquant.markets.market import Market


class BitmexFutureWs(Market):
    def __init__(self, meta_code):
        base_currency, market_currency, symbol = self.parse_meta(meta_code)
        super().__init__(base_currency, market_currency, meta_code, cfg.get_float_config(Constants.BITMEX_FEE))
        self.base_url = Constants.BITMEX_FUTURE_WS_BASE
        self.symbol = symbol
        self.timeout = Constants.OK_HTTP_TIMEOUT
        self.update_flags = {"depth": False}
        self.websocket = None
        self.depth = None
        self.trade = None

    def close_short(self, price, amount):
        return super().close_short(price, amount)

    def get_depth(self):
        super().get_depth()

    def sub_channel(self):
        return super().sub_channel()

    def update(self):
        super().update()

    def get_ticker(self):
        return super().get_ticker()

    def keep_connect(self):
        return super().keep_connect()

    def unset_flags(self, flags):
        super().unset_flags(flags)

    def close_long(self, price, amount):
        return super().close_long(price, amount)

    def long(self, price, amount):
        return super().long(price, amount)

    def check_flags(self, flags):
        return super().check_flags(flags)

    def short(self, price, amount):
        return super().short(price, amount)

    def parse_meta(self, meta_code):
        meta_table = {"btc_usd": ("btc", "usd", "XBTUSD"), }
        return meta_table[meta_code]


