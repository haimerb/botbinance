import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class SymbolFilters:
    symbol: str
    step_size: float
    min_qty: float
    max_qty: float
    tick_size: float
    min_notional: float


def _parse_filters(symbol: str, raw) -> SymbolFilters:
    step_size = 0.0
    min_qty = 0.0
    max_qty = 0.0
    tick_size = 0.0
    min_notional = 0.0

    for f in raw.get("filters", []):
        ftype = f.get("filterType")
        if ftype == "LOT_SIZE":
            step_size = float(f.get("stepSize", 0) or 0)
            min_qty = float(f.get("minQty", 0) or 0)
            max_qty = float(f.get("maxQty", 0) or 0)
        elif ftype == "MARKET_LOT_SIZE":
            market_step = float(f.get("stepSize", 0) or 0)
            if step_size == 0 and market_step > 0:
                step_size = market_step
        elif ftype == "PRICE_FILTER":
            tick_size = float(f.get("tickSize", 0) or 0)
        elif ftype == "NOTIONAL":
            min_notional = float(f.get("minNotional", 0) or 0)

    return SymbolFilters(
        symbol=symbol,
        step_size=step_size,
        min_qty=min_qty,
        max_qty=max_qty,
        tick_size=tick_size,
        min_notional=min_notional,
    )


class ExchangeFilters:
    """Cachea los filtros de exchangeInfo por símbolo y normaliza órdenes."""

    def __init__(self):
        self._filters = {}

    def load(self, client, symbol: str) -> Optional[SymbolFilters]:
        try:
            info = client.exchange_info(symbol=symbol)
            symbols = info.get("symbols", [])
            if not symbols:
                return None
            parsed = _parse_filters(symbol, symbols[0])
            self._filters[symbol] = parsed
            return parsed
        except Exception as e:
            print(f"No se pudieron cargar filtros para {symbol}: {e}")
            return None

    def get(self, symbol: str) -> Optional[SymbolFilters]:
        return self._filters.get(symbol)

    def ensure(self, client, symbol: str) -> Optional[SymbolFilters]:
        if symbol not in self._filters:
            return self.load(client, symbol)
        return self._filters[symbol]

    @staticmethod
    def round_quantity(quantity: float, step_size: float) -> float:
        if step_size <= 0:
            return quantity
        precision = max(0, int(round(-math.log10(step_size))))
        steps = math.floor(round(quantity / step_size, 10))
        return round(steps * step_size, precision)

    @staticmethod
    def round_price(price: float, tick_size: float) -> float:
        if tick_size <= 0:
            return price
        precision = max(0, int(round(-math.log10(tick_size))))
        ticks = round(price / tick_size)
        return round(ticks * tick_size, precision)

    def normalize_order(self, client, symbol: str, quantity: float, price: float = 0.0):
        """Devuelve (qty_ajustada, price_ajustado, error).

        error es None si la orden es válida; si no, un string explicando el motivo.
        """
        filt = self.ensure(client, symbol)
        if filt is None:
            return quantity, price, None

        qty = self.round_quantity(quantity, filt.step_size)
        if qty <= 0:
            return qty, price, f"cantidad {quantity} se redondea a 0 (stepSize={filt.step_size})"
        if filt.min_qty > 0 and qty < filt.min_qty:
            return qty, price, f"cantidad {qty} < minQty {filt.min_qty}"
        if filt.max_qty > 0 and qty > filt.max_qty:
            return qty, price, f"cantidad {qty} > maxQty {filt.max_qty}"

        adjusted_price = price
        if price > 0 and filt.tick_size > 0:
            adjusted_price = self.round_price(price, filt.tick_size)

        if filt.min_notional > 0 and adjusted_price > 0:
            notional = qty * adjusted_price
            if notional < filt.min_notional:
                return qty, adjusted_price, (
                    f"notional {notional:.2f} < minNotional {filt.min_notional}"
                )

        return qty, adjusted_price, None
