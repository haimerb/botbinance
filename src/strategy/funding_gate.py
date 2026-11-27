import math
import statistics
from dataclasses import dataclass
from typing import Optional

from .event_calendar import EconomicCalendar
from .liquidation_pressure import estimate_liquidation_pressure


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
    liquidation_pressure: float = 0.0


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
                  calendar: Optional[EconomicCalendar] = None,
                  persistence_model=None, min_persistence_prob: float = 0.0,
                  liquidation_enabled: bool = True,
                  max_liquidation_pressure: float = 0.85,
                  liquidation_target_rate: float = 0.00005):
        self.min_intervals = min_intervals
        self.min_rate = min_rate
        self.min_net_annual_pct = min_net_annual_pct
        self.max_zscore = max_zscore
        self.max_abs_basis_pct = max_abs_basis_pct
        self.history_window = history_window
        self.calendar = calendar or EconomicCalendar()
        self.persistence_model = persistence_model
        self.min_persistence_prob = min_persistence_prob
        self.liquidation_enabled = liquidation_enabled
        self.max_liquidation_pressure = max_liquidation_pressure
        self.liquidation_target_rate = liquidation_target_rate

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

        pressure = None
        if self.liquidation_enabled:
            pressure = estimate_liquidation_pressure(
                zscore=zscore,
                basis_pct=candidate.basis_pct,
                history=recent,
                max_zscore=self.max_zscore,
                max_basis_pct=self.max_abs_basis_pct,
                target_rate=self.liquidation_target_rate,
            )
        pressure_score = pressure.score if pressure is not None else 0.0
        if pressure_score > self.max_liquidation_pressure:
            return FundingDecision(
                candidate.symbol, False, "liquidaciones_altas", -math.inf,
                pressure_score,
            )

        persistence = None
        if self.persistence_model is not None and self.min_persistence_prob > 0:
            persistence = self.persistence_model.predict(
                candidate.symbol, rate, recent
            )
            if (persistence is not None and
                    persistence < self.min_persistence_prob):
                return FundingDecision(
                    candidate.symbol, False, "persistencia_baja", -math.inf,
                    pressure_score,
                )

        risk = statistics.pstdev(recent) * 10_000 if len(recent) >= 2 else 0.0
        score = candidate.net_annual_pct / (1 + risk)
        if persistence is not None:
            score *= persistence
        return FundingDecision(
            candidate.symbol, True, "ok", score, pressure_score
        )
