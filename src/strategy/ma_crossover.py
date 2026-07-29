import pandas as pd


class MACrossoverStrategy:
    def __init__(self, fast_period: int = 9, slow_period: int = 21):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.last_signal = "HOLD"

    def generate_signal(self, df: pd.DataFrame) -> str:
        if df.empty or len(df) < self.slow_period:
            return "HOLD"

        df = df.copy()
        df["ma_fast"] = df["close"].rolling(window=self.fast_period).mean()
        df["ma_slow"] = df["close"].rolling(window=self.slow_period).mean()

        prev_fast = df["ma_fast"].iloc[-2]
        prev_slow = df["ma_slow"].iloc[-2]
        curr_fast = df["ma_fast"].iloc[-1]
        curr_slow = df["ma_slow"].iloc[-1]

        if prev_fast <= prev_slow and curr_fast > curr_slow:
            self.last_signal = "BUY"
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            self.last_signal = "SELL"
        else:
            self.last_signal = "HOLD"

        return self.last_signal
