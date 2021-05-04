class Constants():
    BITMEX_APIKEY = "bitmex_apikey"
    BITMEX_APISEC = "bitmex_apisec"
    BITMEX_FEE = "bitmex_fee"
    BITMEX_ID = "bitmex_id"
    BITMEX_FUTURE_CLOSE_POSITION = "https://www.bitmex.com/api/v1/order/closePosition"
    BITMEX_FUTURE_LEVER = "https://www.bitmex.com/api/v1/position/leverage"
    BITMEX_FUTURE_ORDER = "https://www.bitmex.com/api/v1/order"
    BITMEX_FUTURE_WS_BASE = "wss://www.bitmex.com/realtime"

    DEV = "dev"
    DQUANT_ENV = "DQUANTENV"

    OKEX_APIKEY = "okex_apikey"
    OKEX_APISEC = "okex_apisec"
    OKEX_FEE = "okex_fee"
    OKEX_FEE_TAKER = "okex_fee_taker"
    OKEX_ID = "okex_id"
    OKEX_MINIMUM_AMOUNT = "okex_minimum_amount"
    OKEX_STRATEGY_ID = "okex_strategy_id"
    OKEX_FUTURE_DELETE_ORDER_REST = "/api/v1/future_cancel.do"
    OKEX_FUTURE_DEPTH_RESOURCE_REST = "/api/v1/future_depth.do"
    OKEX_FUTURE_FOLLOW_PRICE = "okex_future_follow_price"
    OKEX_FUTURE_REST_BASE = "https://www.okex.com"
    OKEX_FUTURE_TICKER_REST = "/api/v1/future_ticker.do"
    OKEX_FUTURE_INDEX_REST = "/api/v1/future_index.do"
    OKEX_FUTURE_TRADE_REST = "/api/v1/future_trade.do?"
    OKEX_FUTURE_TRADES_REST = "/api/v1/future_trades.do"
    OKEX_FUTURE_USERINFO_REST = '/api/v1/future_userinfo.do'
    OKEX_FUTURE_GET_ORDER_REST = "/api/v1/future_order_info.do"
    OKEX_FUTURE_GET_POSITION_REST = "/api/v1/future_position.do"

    OKEX_FUTURE_APIKEY = "okex_future_apikey"
    OKEX_FUTURE_APISEC = "okex_future_apisec"
    OKEX_FUTURE_FEE = "okex_future_fee"
    OKEX_FUTURE_FEE_TAKER = "okex_future_fee_taker"
    OKEX_FUTURE_ID = "okex_future_id"
    OKEX_FUTURE_MINIMUM_AMOUNT = "okex_future_minimum_amount"
    OKEX_FUTURE_STRATEGY_ID = "okex_future_strategy_id"
    OKEX_FUTURE_LOGIN = 'login'
    OKEX_FUTURE_WS_BASE = "wss://real.okex.com:10440/websocket/okexapi"
    OKEX_FUTURE_USERINFO_WS = 'ok_futureusd_userinfo'
    OKEX_FUTURE_DELETE_ORDER_WS = "ok_futureusd_cancel_order"
    OKEX_FUTURE_GET_ORDER_WS = "ok_futureusd_orderinfo"
    OKEX_FUTURE_TRADE_WS = "ok_futureusd_trade"
    OKEX_FUTURE_SUB_USERINFO = 'ok_sub_futureusd_userinfo'
    OKEX_FUTURE_SUB_TRADES = 'ok_sub_futureusd_trades'
    OKEX_FUTURE_SUB_POSITIONS = 'ok_sub_futureusd_positions'

    OKEX_SPOT_WS_BASE = 'wss://real.okex.com:10441/websocket'
    OKEX_SPOT_TRADE_WS = 'ok_spot_order'
    OKEX_SPOT_DELETE_ORDER_WS = 'ok_spot_cancel_order'
    OKEX_SPOT_GET_ORDER_WS = "ok_spot_orderinfo"
    OKEX_SPOT_USERINFO_WS = 'ok_spot_userinfo'
    OKEX_PRICE_PRECISION = 'okex_price_precision'
    OKEX_AMOUNT_PRECISION = 'okex_amount_precision'

    OKEX_SPOT_REST_BASE = 'https://www.okex.com'
    OKEX_SPOT_USERINFO_REST = '/api/v1/userinfo.do'
    OKEX_SPOT_DEPTH_RESOURCE_REST = '/api/v1/depth.do'
    OKEX_SPOT_TRADE_REST = '/api/v1/trade.do'
    OKEX_SPOT_TRADES_REST = '/api/v1/trades.do'
    OKEX_SPOT_DELETE_ORDER_REST = '/api/v1/cancel_order.do'
    OKEX_SPOT_ORDERINFO_REST = '/api/v1/order_info.do'
    OKEX_SPOT_ORDERSINFO_REST = '/api/v1/orders_info.do'
    OKEX_SPOT_TICKER_REST = '/api/v1/ticker.do'
    OKEX_SPOT_WITHDRAW_REST = '/api/v1/withdraw.do'

    BITFINEX_APIKEY = "bitfinex_apikey"
    BITFINEX_APISEC = "bitfinex_apisec"
    BITFINEX_MINIMUM_AMOUNT = "bitfinex_minimum_amount"
    BITFINEX_PRICE_PRECISION = 'bitfinex_price_precision'
    BITFINEX_AMOUNT_PRECISION = 'bitfinex_amount_precision'
    BITFINEX_FEE = 'bitfinex_fee'
    BITFINEX_FEE_TAKER = 'bitfinex_fee_taker'
    BITFINEX_ID = "bitfinex_id"
    BITFINEX_STRATEGY_ID = "bitfinex_strategy_id"
    BITFINEX_SPOT_WS_BASE = 'wss://api.bitfinex.com/ws/2'

    BINANCE_FEE = 'binance_fee'
    BINANCE_FEE_TAKER = 'binance_fee_taker'
    BINANCE_APIKEY = 'binance_apikey'
    BINANCE_APISEC = 'binance_apisec'
    BINANCE_MINIMUM_AMOUNT = "binance_minimum_amount"
    BINANCE_PRICE_PRECISION = 'binance_price_precision'
    BINANCE_AMOUNT_PRECISION = 'binance_amount_precision'
    BINANCE_ID = 'binance_id'
    BINANCE_STRATEGY_ID = "binance_strategy_id"
    BINANCE_SPOT_REST_BASE = 'https://api.binance.com'
    BINANCE_USERINFO_RESOURCE_REST = "/api/v1/account"
    BINANCE_ALLORDERS_RESOURCE_REST = "/api/v3/allOrders"
    BINANCE_OPEN_ORDERS_RESOURCE_REST = "/api/v3/openOrders"
    BINANCE_DEPTH_RESOURCE_REST = "/api/v1/depth"
    BINANCE_TRADE_RESOURCE_REST = "/api/v1/order"
    BINANCE_TRADES_REST = "/api/v1/historicalTrades"

    HUOBI_FEE = 'huobi_fee'
    HUOBI_FEE_TAKER = 'huobi_fee_taker'
    HUOBI_APIKEY = 'huobi_apikey'
    HUOBI_APISEC = 'huobi_apisec'
    HUOBI_ID = 'huobi_id'
    HUOBI_MINIMUM_AMOUNT = "huobi_minimum_amount"
    HUOBI_PRICE_PRECISION = 'huobi_price_precision'
    HUOBI_AMOUNT_PRECISION = 'huobi_amount_precision'
    HUOBI_SPOT_ID = 'huobi_spot_id'
    HUOBI_STRATEGY_ID = "huobi_strategy_id"
    HUOBI_REST_BASE = "https://api.huobipro.com"
    HUOBI_ACCOUNT_BASE = "/v1/account/accounts"
    HUOBI_DEPTH_REST = '/market/depth'
    HUOBI_GET_ORDER_REST = '/v1/order/orders'
    HUOBI_ORDER_REST = '/v1/order/orders/place'
    HUOBI_CANCEL_REST = '/v1/order/orders/batchcancel'
    OK_HTTP_TIMEOUT = 10

    PRO = "PRO"

    REDIS_HOST = "redis_host"
    REDIS_PORT = "redis_port"

    MONITOR = "monitor"
    MONGO_IP = 'mongo_ip'
    MONGO_PORT = 'mongo_port'
    MONGO_USER = 'mongo_username'
    MONGO_PWD = 'mongo_pwd'

    LOG_PATH = 'log_path'

    ORDER_RESULT_ERROR = {
        'timeout': 'timeout',
    }