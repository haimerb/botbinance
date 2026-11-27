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

    def __init__(self, api_key: str = None, api_secret: str = None):
        key = api_key if api_key is not None else BINANCE_API_KEY
        secret = api_secret if api_secret is not None else BINANCE_API_SECRET
        self.client = UMFutures(
            key=key,
            secret=secret,
            base_url=BINANCE_FUTURES_BASE_URL,
        )

    def mark_price(self, symbol: str) -> dict:
        """Devuelve markPrice, indexPrice, lastFundingRate y nextFundingTime."""
        return self.client.mark_price(symbol)

    def funding_rate(self, symbol: str, limit: int = 100) -> list:
        """Historial de funding (más reciente primero en la práctica)."""
        return self.client.funding_rate(symbol=symbol, limit=limit)

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
