from binance.spot import Spot
from src.config import BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_BASE_URL


class TradeExecutor:
    def __init__(self, api_key: str = None, api_secret: str = None):
        key = api_key if api_key is not None else BINANCE_API_KEY
        secret = api_secret if api_secret is not None else BINANCE_API_SECRET
        self.client = Spot(api_key=key, api_secret=secret, base_url=BINANCE_BASE_URL)
        self.last_order = None

    def execute_order(self, side: str, quantity: float, symbol: str = "BTCUSDT", order_type="MARKET"):
        try:
            order = self.client.new_order(
                symbol=symbol,
                side=side,
                type=order_type,
                quantity=quantity
            )
            self.last_order = order
            print(f"Orden ejecutada: {side} {quantity} {symbol}")
            return order
        except Exception as e:
            print(f"Error ejecutando orden: {e}")
            return None

    def get_symbol_price(self, symbol: str = "BTCUSDT") -> float:
        try:
            ticker = self.client.ticker_price(symbol=symbol)
            return float(ticker["price"])
        except Exception as e:
            print(f"Error obteniendo precio: {e}")
            return 0.0
