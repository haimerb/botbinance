import math

from src.strategy.funding_arbitrage import (
    annualize_funding,
    evaluate_opportunity,
    net_annual_pct,
    should_close,
)


def test_annualize_funding_real_rate():
    # 0.0052% por 8h (media real de BTC en los últimos 5 meses)
    assert abs(annualize_funding(0.000052) - 5.694) < 0.001


def test_net_annual_amortizes_costs_over_hold_period():
    rate = 0.0001
    net_30 = net_annual_pct(rate, 0.0004, 0.0004, 30)
    net_365 = net_annual_pct(rate, 0.0004, 0.0004, 365)
    assert net_365 > net_30
    assert net_365 < annualize_funding(rate)


def test_net_annual_with_zero_hold_is_minus_inf():
    assert net_annual_pct(0.0001, 0, 0, 0) == -math.inf


def test_evaluate_returns_opportunity_for_realistic_data():
    data = {
        "lastFundingRate": "0.0001",
        "markPrice": "61757.4",
        "indexPrice": "61782.5",
        "nextFundingTime": 1795766400000,
    }
    opp = evaluate_opportunity("BTCUSDT", data, min_annual_pct=5.0, hold_days=30)
    assert opp is not None
    assert opp.symbol == "BTCUSDT"
    assert opp.funding_rate == 0.0001
    assert opp.annual_pct > 10
    assert opp.annual_net_pct > 5
    assert opp.basis_pct < 0
    assert opp.next_funding_time == 1795766400000


def test_evaluate_rejects_low_funding():
    data = {"lastFundingRate": "0.00001"}
    assert evaluate_opportunity("BTCUSDT", data, min_annual_pct=8.0) is None


def test_evaluate_rejects_negative_funding():
    assert evaluate_opportunity("BTCUSDT", {"lastFundingRate": "-0.0001"}) is None


def test_evaluate_rejects_missing_or_invalid_rate():
    assert evaluate_opportunity("BTCUSDT", {}) is None
    assert evaluate_opportunity("BTCUSDT", {"lastFundingRate": "abc"}) is None


def test_evaluate_handles_missing_prices():
    opp = evaluate_opportunity("BTCUSDT", {"lastFundingRate": "0.0001"},
                               min_annual_pct=0)
    assert opp is not None
    assert opp.basis_pct is None


def test_should_close_on_negative_funding():
    assert should_close(-0.0001) is True
    assert should_close(-0.0001, exit_if_negative=False) is False


def test_should_close_on_annual_stop():
    # 0.00002 -> ~2.19% anual; stop en 5% debe cerrar
    assert should_close(0.00002, stop_annual_pct=5.0) is True
    assert should_close(0.0001, stop_annual_pct=5.0) is False
