from dataclasses import dataclass
from typing import Optional

from binance.spot import Spot
from src.config import BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_BASE_URL
from src.execution.exchange_filters import ExchangeFilters


@dataclass
class OrderResult:
    ok: bool
    side: str
    symbol: str
    quantity: float
    order_id: Optional[int] = None
    status: Optional[str] = None
    filled_qty: float = 0.0
    avg_price: float = 0.0
    error: Optional[str] = None

    @staticmethod
    def failure(side: str, symbol: str, quantity: float, error: str) -> "OrderResult":
        return OrderResult(ok=False, side=side, symbol=symbol, quantity=quantity, error=error)


class TradeExecutor:
    def __init__(self, api_key: str = None, api_secret: str = None):
        key = api_key if api_key is not None else BINANCE_API_KEY
        secret = api_secret if api_secret is not None else BINANCE_API_SECRET
        self.client = Spot(api_key=key, api_secret=secret, base_url=BINANCE_BASE_URL)
        self.last_order = None
        self.filters = ExchangeFilters()

    def execute_order(
        self, side: str, quantity: float, symbol: str = "BTCUSDT", order_type="MARKET"
    ) -> OrderResult:
        qty = quantity
        if order_type == "MARKET":
            ref_price = self.get_symbol_price(symbol)
            qty, _price, error = self.filters.normalize_order(
                self.client, symbol, quantity, ref_price
            )
            if error:
                print(f"Orden rechazada localmente ({symbol} {side}): {error}")
                return OrderResult.failure(side, symbol, quantity, error)

        try:
            order = self.client.new_order(
                symbol=symbol,
                side=side,
                type=order_type,
                quantity=qty
            )
            self.last_order = order
            filled_qty = float(order.get("executedQty", 0) or 0)
            avg_price = self._avg_fill_price(order, fallback_qty=filled_qty)
            print(f"Orden ejecutada: {side} {filled_qty} {symbol} @ {avg_price}")
            return OrderResult(
                ok=True,
                side=side,
                symbol=symbol,
                quantity=qty,
                order_id=order.get("orderId"),
                status=order.get("status"),
                filled_qty=filled_qty,
                avg_price=avg_price,
            )
        except Exception as e:
            message = getattr(e, "error_message", None) or str(e)
            print(f"Error ejecutando orden: {message}")
            return OrderResult.failure(side, symbol, quantity, message)

    @staticmethod
    def _avg_fill_price(order: dict, fallback_qty: float) -> float:
        fills = order.get("fills") or []
        total_qty = sum(float(f.get("qty", 0) or 0) for f in fills)
        if total_qty > 0:
            notional = sum(float(f.get("price", 0) or 0) * float(f.get("qty", 0) or 0) for f in fills)
            return notional / total_qty
        cump = order.get("cummulativeQuoteQty")
        if cump is not None and fallback_qty > 0:
            return float(cump) / fallback_qty
        return 0.0

    def get_symbol_price(self, symbol: str = "BTCUSDT") -> float:
        try:
            ticker = self.client.ticker_price(symbol=symbol)
            return float(ticker["price"])
        except Exception as e:
            print(f"Error obteniendo precio: {e}")
            return 0.0
