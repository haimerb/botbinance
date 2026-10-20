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


def test_buy_and_hold_benchmark_present():
    df = make_df(n=100, trend=0.001)
    engine = BacktestEngine({"initial_balance": 10000.0, "trade_quantity": 1.0})
    result = engine.run(df, symbol="BTCUSDT")
    assert "buy_hold_return_pct" in result
    assert "excess_return_pct" in result
    assert "beats_buy_hold" in result
    assert isinstance(result["beats_buy_hold"], bool)


def test_buy_and_hold_positive_in_uptrend():
    df = make_df(n=100, trend=0.001)
    engine = BacktestEngine({"initial_balance": 10000.0, "trade_quantity": 1.0})
    result = engine.run(df, symbol="BTCUSDT")
    assert result["buy_hold_return_pct"] > 0
    assert result["buy_hold_max_drawdown_pct"] >= 0


def test_buy_and_hold_zero_flat_market():
    df = make_df(n=50, trend=0.0)
    engine = BacktestEngine({"initial_balance": 10000.0, "trade_quantity": 1.0})
    result = engine.run(df, symbol="BTCUSDT")
    assert result["buy_hold_return_pct"] <= 0


def test_buy_and_hold_equity_applies_costs():
    engine = BacktestEngine({"initial_balance": 10000.0, "commission_pct": 0.001, "slippage_pct": 0.0})
    equity = engine._buy_and_hold_equity([100.0, 100.0, 100.0])
    assert equity[-1] < 10000.0


def test_walk_forward_reports_buy_hold():
    df = make_df(n=200)
    result = walk_forward_analysis(df, lambda: BacktestEngine({"trade_quantity": 1.0}), n_splits=4)
    assert "avg_buy_hold_return_pct" in result
    assert "beats_buy_hold" in result
    assert "folds_beating_buy_hold" in result


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


def make_ohlcv_df(n=300, seed=1):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.standard_normal(n))
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=n, freq="h"),
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": rng.random(n) * 1000,
    })


def test_generate_signals_adds_signal_column():
    df = make_ohlcv_df()
    engine = BacktestEngine()
    out = engine.generate_signals(df)
    assert "signal" in out.columns
    assert set(out["signal"].unique()).issubset({"BUY", "SELL", "HOLD"})
    assert len(out) == len(df)


def test_run_generates_signals_when_missing():
    df = make_ohlcv_df()
    engine = BacktestEngine({"trade_quantity": 0.5})
    result = engine.run(df, symbol="TESTUSDT")
    assert "error" not in result
    assert "total_trades" in result


def test_generate_signals_with_custom_fn():
    df = make_ohlcv_df()
    engine = BacktestEngine()
    out = engine.generate_signals(df, signal_fn=lambda d: ["BUY"] * len(d))
    assert (out["signal"] == "BUY").all()
