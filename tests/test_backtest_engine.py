import pandas as pd
import numpy as np

from src.backtest.engine import BacktestEngine, walk_forward_analysis


def make_df(n=100, trend=0.001):
    prices = [100.0]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + trend))
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="h").astype(str),
        "close": prices,
        "open": prices,
        "high": [p * 1.01 for p in prices],
        "low": [p * 0.99 for p in prices],
        "volume": [100] * n,
        "signal": ["BUY"] * n,
    })


def test_engine_runs_and_returns_metrics():
    df = make_df()
    engine = BacktestEngine({"initial_balance": 10000.0, "trade_quantity": 1.0})
    result = engine.run(df, symbol="BTCUSDT")
    assert "error" not in result
    assert "sharpe_ratio" in result
    assert "sortino_ratio" in result
    assert "max_drawdown_pct" in result
    assert "profit_factor" in result
    assert result["commission_pct"] == 0.001
    assert result["slippage_pct"] == 0.0005


def test_slippage_is_applied():
    df = make_df(trend=0.0)
    engine = BacktestEngine({"slippage_pct": 0.05, "commission_pct": 0.0, "trade_quantity": 1.0})
    assert engine._apply_slippage(100.0, "BUY") == 105.0
    assert engine._apply_slippage(100.0, "SELL") == 95.0


def test_empty_df_returns_error():
    engine = BacktestEngine()
    result = engine.run(pd.DataFrame(), symbol="BTCUSDT")
    assert "error" in result


def test_max_drawdown_calculation():
    equity = np.array([100, 120, 90, 110])
    dd = BacktestEngine._max_drawdown(equity)
    assert dd == 25.0


def test_sharpe_zero_variance():
    returns = np.array([0.0, 0.0, 0.0])
    assert BacktestEngine._sharpe(returns) == 0.0


def test_walk_forward_produces_folds():
    df = make_df(n=200)
    result = walk_forward_analysis(df, lambda: BacktestEngine({"trade_quantity": 1.0}), n_splits=4)
    assert "error" not in result
    assert len(result["folds"]) >= 2
    assert "avg_return_pct" in result
    assert "consistency_pct" in result


def test_time_exit_closes_position():
    df = make_df(n=48, trend=0.0)
    engine = BacktestEngine({
        "trade_quantity": 1.0,
        "commission_pct": 0.0,
        "slippage_pct": 0.0,
        "time_exit_hours": 5,
        "enable_trailing": False,
        "stop_loss_pct": 0.5,
        "take_profit_pct": 0.5,
    })
    result = engine.run(df, symbol="BTCUSDT")
    assert "error" not in result
    assert result["exits"] > 0


def test_elapsed_hours_helper():
    assert BacktestEngine._elapsed_hours("2024-01-01 00:00:00", "2024-01-01 06:00:00") == 6.0
    assert BacktestEngine._elapsed_hours(None, "2024-01-01") is None
    assert BacktestEngine._elapsed_hours("no-fecha", "2024-01-01") is None