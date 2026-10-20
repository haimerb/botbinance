import pandas as pd
import pytest

from src.risk.portfolio_manager import PortfolioManager, compute_kelly_fraction


def test_equal_weights():
    pm = PortfolioManager(mode="equal")
    weights = pm.compute_weights(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    assert pytest.approx(sum(weights.values()), abs=1e-3) == 1.0
    assert pytest.approx(weights["BTCUSDT"], abs=1e-3) == 1 / 3


def test_inverse_vol_prefers_low_volatility():
    pm = PortfolioManager(mode="inverse_vol")
    weights = pm.compute_weights(
        ["BTCUSDT", "ETHUSDT"],
        volatilities={"BTCUSDT": 0.01, "ETHUSDT": 0.05},
    )
    assert weights["BTCUSDT"] > weights["ETHUSDT"]
    assert pytest.approx(sum(weights.values()), abs=1e-3) == 1.0


def test_confidence_weights():
    pm = PortfolioManager(mode="confidence")
    weights = pm.compute_weights(
        ["BTCUSDT", "ETHUSDT"],
        confidences={"BTCUSDT": 0.9, "ETHUSDT": 0.3},
    )
    assert weights["BTCUSDT"] > weights["ETHUSDT"]


def test_allocate_capital_respects_cap():
    pm = PortfolioManager(mode="equal")
    alloc = pm.allocate_capital(10000.0, ["BTCUSDT", "ETHUSDT"], max_per_symbol_pct=0.4)
    assert alloc["BTCUSDT"] == 4000.0
    assert alloc["ETHUSDT"] == 4000.0


def test_volatility_from_prices():
    vol_low = PortfolioManager.compute_volatility([100, 100.1, 100.2, 100.1, 100.3])
    vol_high = PortfolioManager.compute_volatility([100, 110, 90, 120, 80])
    assert vol_high > vol_low


def test_kelly_fraction_bounds():
    assert compute_kelly_fraction(0.6, 0.03, 0.02) > 0
    assert compute_kelly_fraction(0.0, 0.03, 0.02) == 0.0
    assert compute_kelly_fraction(0.6, 0.03, 0.0) == 0.0
    assert compute_kelly_fraction(0.9, 0.10, 0.01) <= 0.25