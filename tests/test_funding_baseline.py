from src.backtest.funding_baseline import compare_with_simple, run_funding_backtest
from src.strategy.event_calendar import _to_ms
from src.strategy.funding_gate import FundingGate

BASE = _to_ms("2026-11-20T00:00:00Z")


def _rows():
    rows = []
    episode = (
        [-0.0001] * 3
        + [0.0008]
        + [0.00002] * 3
        + [0.0003] * 8
        + [-0.0002]
    )
    rates = episode * 3
    for i, rate in enumerate(rates):
        local = i % len(episode)
        basis = 1.0 if 3 <= local <= 6 else 0.05
        rows.append({
            "funding_time": BASE + i * 8 * 3_600_000,
            "funding_rate": rate,
            "basis_pct": basis,
        })
    return rows


def test_backtest_simple_carry_includes_spike_and_loses():
    result = run_funding_backtest(_rows(), notional=100)
    assert result["trades"] == 3
    assert result["net_pnl"] < 0


def test_gate_beats_simple_with_same_costs():
    gate = FundingGate(min_net_annual_pct=8.0, max_abs_basis_pct=0.5)
    result = compare_with_simple(_rows(), gate, notional=100)
    assert result["gate"]["net_pnl"] > 0
    assert result["gate"]["trades"] >= 3
    assert result["accepted"]
    assert result["delta_net_pnl"] > 0
