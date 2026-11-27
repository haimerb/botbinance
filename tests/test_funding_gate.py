import math

from src.strategy.event_calendar import _to_ms
from src.strategy.funding_gate import (
    FundingCandidate,
    FundingDecision,
    FundingGate,
    funding_zscore,
    rank_candidates,
    sustained_funding,
)

TS = _to_ms("2026-11-20T00:00:00Z")
HISTORY = [0.00008 + i * 0.000002 for i in range(12)]


def _candidate(**kwargs):
    values = dict(
        symbol="SOLUSDT",
        funding_rate=0.0001,
        net_annual_pct=10.0,
        funding_time=TS,
        basis_pct=0.05,
    )
    values.update(kwargs)
    return FundingCandidate(**values)


def test_sustained_funding_rejects_single_positive_interval():
    assert not sustained_funding(0.0001, [-0.0001, -0.0001], 3)
    assert sustained_funding(0.0001, [0.00008, 0.00009], 3)


def test_funding_zscore_detects_extreme_rate():
    assert funding_zscore(0.0001, HISTORY) is not None
    assert funding_zscore(0.0001, [0.0001] * 3) is None


def test_gate_accepts_steady_funding():
    decision = FundingGate().evaluate(_candidate(), HISTORY)
    assert decision.allowed
    assert decision.reason == "ok"
    assert decision.score > 0


def test_gate_rejects_extreme_funding():
    decision = FundingGate().evaluate(
        _candidate(funding_rate=0.003), HISTORY
    )
    assert not decision.allowed
    assert decision.reason == "funding_extremo"


def test_gate_rejects_wide_basis():
    decision = FundingGate().evaluate(_candidate(basis_pct=1.2), HISTORY)
    assert not decision.allowed
    assert decision.reason == "basis_fuera_de_rango"


def test_gate_rejects_event_window():
    decision = FundingGate().evaluate(
        _candidate(funding_time=_to_ms("2026-11-10T13:30:00Z")), HISTORY
    )
    assert not decision.allowed
    assert decision.reason.startswith("evento_")


def test_gate_rejects_insufficient_history():
    decision = FundingGate().evaluate(_candidate(), [0.0001])
    assert not decision.allowed
    assert decision.reason == "funding_no_sostenido"


def test_rank_candidates_puts_allowed_first_and_sorts_by_score():
    decisions = [
        FundingDecision("B", False, "basis_fuera_de_rango", math.inf),
        FundingDecision("C", True, "ok", 8.0),
        FundingDecision("A", True, "ok", 12.0),
    ]
    ranked = rank_candidates(decisions)
    assert [d.symbol for d in ranked] == ["A", "C", "B"]
