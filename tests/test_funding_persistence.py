from src.strategy.event_calendar import _to_ms
from src.strategy.funding_gate import FundingCandidate, FundingGate
from src.strategy.funding_persistence import FundingPersistenceModel

TS = _to_ms("2026-11-20T00:00:00Z")


def test_model_learns_repeated_mid_streak_persistence():
    rates = [0.0001, 0.0001, 0.0001, 0.0002, -0.0001] * 30
    model = FundingPersistenceModel(min_samples=5).fit({"SOLUSDT": rates})
    probability = model.predict("SOLUSDT", 0.0001, [0.0001, 0.0001])
    assert probability > 0.9


def test_gate_rejects_low_persistence_probability():
    model = FundingPersistenceModel(min_samples=5)
    model.counts[("SOLUSDT", ("mid", 4), False)] = 30
    gate = FundingGate(
        persistence_model=model,
        min_persistence_prob=0.6,
    )
    candidate = FundingCandidate(
        symbol="SOLUSDT",
        funding_rate=0.0001,
        net_annual_pct=10.0,
        funding_time=TS,
    )
    decision = gate.evaluate(candidate, [0.00008, 0.00009, 0.0001])
    assert not decision.allowed
    assert decision.reason == "persistencia_baja"


def test_gate_keeps_score_when_model_has_no_samples():
    gate = FundingGate(
        persistence_model=FundingPersistenceModel(min_samples=20),
        min_persistence_prob=0.6,
    )
    candidate = FundingCandidate(
        symbol="BTCUSDT",
        funding_rate=0.0001,
        net_annual_pct=10.0,
        funding_time=TS,
    )
    decision = gate.evaluate(candidate, [0.00008, 0.00009, 0.0001])
    assert decision.allowed
    assert decision.score > 0
