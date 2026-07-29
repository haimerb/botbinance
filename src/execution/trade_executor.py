from binance.client import Client
from binance.exceptions import BinanceAPIException
from src.config import BINANCE_API_KEY, BINANCE_API_SECRET, USE_TESTNET


class TradeExecutor:
    def __init__(self):
        self.client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)
        if USE_TESTNET:
            self.client.API_URL = "https://testnet.binance.vision/api"
        self.last_order = None

    def execute_order(self, side: str, quantity: float, symbol: str = "BTCUSDT", order_type="MARKET"):
        try:
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                type=order_type,
                quantity=quantity
            )
            self.last_order = order
            print(f"Orden ejecutada: {side} {quantity} {symbol}")
            return order
        except BinanceAPIException as e:
            print(f"Error ejecutando orden: {e}")
            return None

    def get_symbol_price(self, symbol: str = "BTCUSDT") -> float:
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker["price"])
        except BinanceAPIException as e:
            print(f"Error obteniendo precio: {e}")
            return 0.0
