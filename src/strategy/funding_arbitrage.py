import math
from dataclasses import dataclass
from typing import Optional

FUNDINGS_PER_DAY = 3
DAYS_PER_YEAR = 365


@dataclass
class FundingOpportunity:
    symbol: str
    funding_rate: float
    annual_pct: float
    annual_net_pct: float
    next_funding_time: Optional[int] = None
    mark_price: Optional[float] = None
    index_price: Optional[float] = None

    @property
    def basis_pct(self) -> Optional[float]:
        """Prima del futuro sobre el índice; None si no hay precios."""
        if not self.mark_price or not self.index_price:
            return None
        return (self.mark_price / self.index_price - 1) * 100


def annualize_funding(rate: float) -> float:
    """Funding por ciclo de 8h a porcentaje anual."""
    return rate * FUNDINGS_PER_DAY * DAYS_PER_YEAR * 100


def net_annual_pct(rate: float, entry_cost: float, exit_cost: float,
                   hold_days: float) -> float:
    """Rentabilidad anualizada tras amortizar entrada y salida.

    ``entry_cost`` y ``exit_cost`` son fracciones del notional (0.0004 = 0.04%).
    Si ``hold_days`` es 0 o negativo se devuelve -inf para no abrir.
    """
    if hold_days <= 0:
        return -math.inf
    gross = rate * FUNDINGS_PER_DAY * DAYS_PER_YEAR
    costs = (entry_cost + exit_cost) / hold_days * DAYS_PER_YEAR
    return (gross - costs) * 100


def evaluate_opportunity(symbol: str, mark_data: dict, *,
                         min_annual_pct: float = 8.0,
                         entry_cost: float = 0.0004,
                         exit_cost: float = 0.0004,
                         hold_days: float = 30.0) -> Optional[FundingOpportunity]:
    """Convierte la respuesta de ``mark_price`` en una oportunidad.

    Devuelve None si faltan datos, el funding no es positivo o no supera
    el umbral neto exigido.
    """
    raw = mark_data.get("lastFundingRate")
    if raw is None:
        return None
    try:
        rate = float(raw)
    except (TypeError, ValueError):
        return None
    if rate <= 0:
        return None

    net = net_annual_pct(rate, entry_cost, exit_cost, hold_days)
    if net < min_annual_pct:
        return None

    def as_float(key):
        value = mark_data.get(key)
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    next_time = mark_data.get("nextFundingTime")
    return FundingOpportunity(
        symbol=symbol,
        funding_rate=rate,
        annual_pct=annualize_funding(rate),
        annual_net_pct=net,
        next_funding_time=int(next_time) if next_time is not None else None,
        mark_price=as_float("markPrice"),
        index_price=as_float("indexPrice"),
    )


def should_close(funding_rate: float, exit_if_negative: bool = True,
                 stop_annual_pct: float = 0.0) -> bool:
    """Decisión de cierre para una posición abierta.

    Se cierra si el funding se vuelve negativo (configurable) o si la
    rentabilidad anualizada cae por debajo del stop.
    """
    if exit_if_negative and funding_rate < 0:
        return True
    if stop_annual_pct <= 0:
        return False
    return annualize_funding(funding_rate) < stop_annual_pct
