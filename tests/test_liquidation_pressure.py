from src.strategy.funding_gate import FundingCandidate, FundingGate
from src.strategy.liquidation_pressure import estimate_liquidation_pressure


def test_estimate_liquidation_pressure_combines_signals():
    pressure = estimate_liquidation_pressure(
        zscore=1.0,
        basis_pct=0.25,
        history=[0.0001, 0.0003],
        max_zscore=2.0,
        max_basis_pct=0.5,
        target_rate=0.0001,
    )
    assert pressure.score == 0.55
    assert pressure.source == "funding_basis_proxy"


def test_gate_rejects_high_liquidation_pressure():
    gate = FundingGate(
        max_zscore=2.5,
        max_abs_basis_pct=0.5,
        max_liquidation_pressure=0.2,
    )
    candidate = FundingCandidate(
        symbol="SOLUSDT",
        funding_rate=0.0001,
        net_annual_pct=10.0,
        funding_time=1_800_000_000_000,
        basis_pct=0.49,
    )
    decision = gate.evaluate(candidate, [0.0001] * 10)
    assert decision.allowed is False
    assert decision.reason == "liquidaciones_altas"
    assert decision.liquidation_pressure > 0.2


def test_gate_can_disable_liquidation_filter():
    gate = FundingGate(
        max_liquidation_pressure=0.2,
        liquidation_enabled=False,
    )
    candidate = FundingCandidate(
        symbol="SOLUSDT",
        funding_rate=0.0001,
        net_annual_pct=10.0,
        funding_time=1_800_000_000_000,
        basis_pct=0.49,
    )
    decision = gate.evaluate(candidate, [0.0001] * 10)
    assert decision.allowed is True
    assert decision.liquidation_pressure == 0.0
