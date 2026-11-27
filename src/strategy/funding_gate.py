import math
import statistics
from dataclasses import dataclass
from typing import Optional

from .event_calendar import EconomicCalendar


@dataclass(frozen=True)
class FundingCandidate:
    symbol: str
    funding_rate: float
    net_annual_pct: float
    funding_time: int
    basis_pct: Optional[float] = None


@dataclass(frozen=True)
class FundingDecision:
    symbol: str
    allowed: bool
    reason: str
    score: float


def funding_zscore(rate: float, history: list) -> Optional[float]:
    """Z-score del funding actual frente a su historial reciente."""
    if len(history) < 3:
        return None
    mean = statistics.fmean(history)
    std = statistics.pstdev(history)
    if std == 0:
        return None
    return (rate - mean) / std


def sustained_funding(rate: float, history: list, min_intervals: int,
                      min_rate: float = 0.0) -> bool:
    """Exige funding positivo en los últimos N intervalos."""
    if min_intervals <= 0:
        return True
    trailing = list(history)[-(min_intervals - 1):] + [rate]
    if len(trailing) < min_intervals:
        return False
    if any(value <= 0 for value in trailing):
        return False
    return statistics.fmean(trailing) >= min_rate


def rank_candidates(decisions: list) -> list:
    """Ordena por score riesgo-ajustado; los rechazados quedan al final."""
    return sorted(decisions, key=lambda d: (not d.allowed, -d.score, d.symbol))


class FundingGate:
    """Filtro de entrada y score de rotación para funding carry."""

    def __init__(self, *, min_intervals: int = 3, min_rate: float = 0.0,
                 min_net_annual_pct: float = 0.0, max_zscore: float = 2.5,
                 max_abs_basis_pct: float = 0.5, history_window: int = 30,
                 calendar: Optional[EconomicCalendar] = None):
        self.min_intervals = min_intervals
        self.min_rate = min_rate
        self.min_net_annual_pct = min_net_annual_pct
        self.max_zscore = max_zscore
        self.max_abs_basis_pct = max_abs_basis_pct
        self.history_window = history_window
        self.calendar = calendar or EconomicCalendar()

    def evaluate(self, candidate: FundingCandidate, history: list) -> FundingDecision:
        rate = candidate.funding_rate
        if rate <= 0:
            return FundingDecision(candidate.symbol, False,
                                   "funding_no_positivo", -math.inf)
        if candidate.net_annual_pct < self.min_net_annual_pct:
            return FundingDecision(candidate.symbol, False,
                                   "neto_insuficiente", -math.inf)
        if not sustained_funding(rate, history, self.min_intervals,
                                 self.min_rate):
            return FundingDecision(candidate.symbol, False,
                                   "funding_no_sostenido", -math.inf)

        recent = list(history)[-self.history_window:]
        zscore = funding_zscore(rate, recent)
        if zscore is not None and zscore > self.max_zscore:
            return FundingDecision(candidate.symbol, False,
                                   "funding_extremo", -math.inf)

        if (candidate.basis_pct is not None and
                abs(candidate.basis_pct) > self.max_abs_basis_pct):
            return FundingDecision(candidate.symbol, False,
                                   "basis_fuera_de_rango", -math.inf)

        event = self.calendar.label_at(candidate.funding_time)
        if event:
            return FundingDecision(candidate.symbol, False,
                                   f"evento_{event.lower()}", -math.inf)

        risk = statistics.pstdev(recent) * 10_000 if len(recent) >= 2 else 0.0
        score = candidate.net_annual_pct / (1 + risk)
        return FundingDecision(candidate.symbol, True, "ok", score)
