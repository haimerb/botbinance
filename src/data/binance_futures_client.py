from binance.um_futures import UMFutures

from src.config import (
    BINANCE_API_KEY,
    BINANCE_API_SECRET,
    BINANCE_FUTURES_BASE_URL,
)


class BinanceFuturesClient:
    """Cliente de futuros USDⓈ-M para arbitraje de funding.

    Acepta credenciales explícitas (las del usuario, descifradas en el runner)
    y cae a las variables globales cuando no se pasan, igual que
    ``BinanceDataClient``.
    """

    def __init__(self, api_key: str = None, api_secret: str = None,
                 base_url: str = None):
        key = api_key if api_key is not None else BINANCE_API_KEY
        secret = api_secret if api_secret is not None else BINANCE_API_SECRET
        self.client = UMFutures(
            key=key,
            secret=secret,
            base_url=base_url or BINANCE_FUTURES_BASE_URL,
        )

    def mark_price(self, symbol: str) -> dict:
        """Devuelve markPrice, indexPrice, lastFundingRate y nextFundingTime."""
        return self.client.mark_price(symbol)

    def funding_rate(self, symbol: str, limit: int = 100, **kwargs) -> list:
        """Historial de funding; admite ``startTime``/``endTime``."""
        return self.client.funding_rate(symbol=symbol, limit=limit, **kwargs)

    def mark_price_klines(self, symbol: str, interval: str, **kwargs) -> list:
        return self.client.mark_price_klines(symbol=symbol, interval=interval, **kwargs)

    def index_price_klines(self, pair: str, interval: str, **kwargs) -> list:
        return self.client.index_price_klines(pair=pair, interval=interval, **kwargs)

    def open_interest_hist(self, symbol: str, period: str, **kwargs) -> list:
        return self.client.open_interest_hist(symbol=symbol, period=period, **kwargs)

    def exchange_info(self, symbol: str = None) -> dict:
        return self.client.exchange_info(symbol=symbol)

    def balance(self) -> list:
        return self.client.balance()

    def positions(self) -> list:
        return self.client.position_risk()

    def set_leverage(self, symbol: str, leverage: int) -> dict:
        return self.client.change_leverage(symbol=symbol, leverage=leverage)

    def set_margin_type(self, symbol: str, margin_type: str = "ISOLATED") -> dict:
        return self.client.change_margin_type(symbol=symbol, marginType=margin_type)

    def place_order(self, symbol: str, side: str, quantity: float,
                    order_type: str = "MARKET", **kwargs) -> dict:
        """Orden de futuros. ``side`` es BUY/SELL (SELL abre el short)."""
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }
        params.update(kwargs)
        return self.client.new_order(**params)
