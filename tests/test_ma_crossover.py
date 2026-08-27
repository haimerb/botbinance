import pandas as pd
from src.strategy.ma_crossover import MACrossoverStrategy


def make_df(closes):
    return pd.DataFrame({
        "close": closes,
        "high": [c * 1.01 for c in closes],
        "low": [c * 0.99 for c in closes],
        "volume": [100] * len(closes),
    })


def test_buy_signal():
    prices = [10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
              10, 10, 10, 10, 9, 9, 9, 9, 9, 20]
    df = make_df(prices)
    strat = MACrossoverStrategy(fast_period=5, slow_period=10)
    signal = strat.generate_signal(df)
    assert signal == "BUY"


def test_hold_on_insufficient_data():
    df = make_df([10, 11, 12])
    strat = MACrossoverStrategy(fast_period=5, slow_period=10)
    signal = strat.generate_signal(df)
    assert signal == "HOLD"


def test_empty_dataframe():
    strat = MACrossoverStrategy()
    signal = strat.generate_signal(pd.DataFrame())
    assert signal == "HOLD"
