import numpy as np
import pandas as pd
from typing import Tuple, Optional
from dataclasses import dataclass


@dataclass
class SignalResult:
    signal: str
    confidence: float
    trend_strength: float
    slope: float
    details: dict


class TheilSenRegression:
    def __init__(self, window: int = 20):
        self.window = window

    def fit_predict(self, y: np.ndarray) -> Tuple[float, float]:
        n = len(y)
        if n < 2:
            return 0.0, 0.0

        slopes = []
        for i in range(n):
            for j in range(i + 1, n):
                if j != i:
                    slopes.append((y[j] - y[i]) / (j - i))

        if not slopes:
            return 0.0, 0.0

        median_slope = np.median(slopes)
        intercept = np.median(y - median_slope * np.arange(n))

        residuals = y - (median_slope * np.arange(n) + intercept)
        mad = np.median(np.abs(residuals - np.median(residuals)))
        slope_std = 1.4826 * mad if mad > 0 else 1e-10

        return median_slope, slope_std

    def predict_trend(self, series: pd.Series) -> Tuple[float, float, float]:
        if len(series) < self.window:
            return 0.0, 0.0, 0.0

        window_data = series.iloc[-self.window:].values
        slope, slope_std = self.fit_predict(window_data)

        if slope_std > 0:
            t_stat = abs(slope) / slope_std
            confidence = min(t_stat / 3.0, 1.0)
        else:
            confidence = 0.0

        return slope, confidence, slope_std


class EnhancedStrategy:
    def __init__(
        self,
        theil_window: int = 20,
        ema_fast: int = 9,
        ema_slow: int = 21,
        rsi_period: int = 14,
        rsi_oversold: float = 30,
        rsi_overbought: float = 70,
        atr_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bb_period: int = 20,
        bb_std: float = 2.0,
        volume_period: int = 20,
        trend_confirmation_periods: int = 3,
        # Weights for each indicator
        w_theil: float = 1.5,
        w_macd: float = 1.2,
        w_bb: float = 1.0,
        w_volume: float = 0.8,
        w_rsi: float = 1.0,
        w_ema: float = 1.0,
    ):
        self.theil_window = theil_window
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.atr_period = atr_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.volume_period = volume_period
        self.trend_confirmation_periods = trend_confirmation_periods

        # Weights
        self.w_theil = w_theil
        self.w_macd = w_macd
        self.w_bb = w_bb
        self.w_volume = w_volume
        self.w_rsi = w_rsi
        self.w_ema = w_ema
        self.total_weight = w_theil + w_macd + w_bb + w_volume + w_rsi + w_ema

        self.theil = TheilSenRegression(window=theil_window)
        self.last_signal = "HOLD"
        self.signal_history = []

    def _calculate_ema(self, series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    def _calculate_rsi(self, series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.inf)
        return 100 - (100 / (1 + rs))

    def _calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def _calculate_macd(self, series: pd.Series, fast: int, slow: int, signal: int) -> Tuple[pd.Series, pd.Series, pd.Series]:
        fast_ema = series.ewm(span=fast, adjust=False).mean()
        slow_ema = series.ewm(span=slow, adjust=False).mean()
        macd = fast_ema - slow_ema
        signal_line = macd.ewm(span=signal, adjust=False).mean()
        histogram = macd - signal_line
        return macd, signal_line, histogram

    def _calculate_bollinger(self, series: pd.Series, period: int, std: float) -> Tuple[pd.Series, pd.Series, pd.Series]:
        middle = series.rolling(window=period).mean()
        std_dev = series.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return middle, upper, lower

    def _calculate_volume_profile(self, df: pd.DataFrame, period: int) -> dict:
        vol_sma = df["volume"].rolling(window=period).mean()
        current_vol = df["volume"].iloc[-1]
        avg_vol = vol_sma.iloc[-1] if not pd.isna(vol_sma.iloc[-1]) else df["volume"].mean()
        
        vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
        
        price_change = df["close"].diff()
        obv = (np.sign(price_change) * df["volume"]).fillna(0).cumsum()
        obv_sma = obv.rolling(window=period).mean()
        
        vwap = (df["close"] * df["volume"]).rolling(window=period).sum() / df["volume"].rolling(window=period).sum()
        vwap_current = vwap.iloc[-1] if not pd.isna(vwap.iloc[-1]) else df["close"].iloc[-1]
        
        return {
            "vol_ratio": vol_ratio,
            "obv": obv.iloc[-1] if not pd.isna(obv.iloc[-1]) else 0,
            "obv_sma": obv_sma.iloc[-1] if not pd.isna(obv_sma.iloc[-1]) else 0,
            "vwap": vwap_current,
            "price_vs_vwap": df["close"].iloc[-1] / vwap_current - 1 if vwap_current > 0 else 0,
        }

    def _calculate_atr(self, df: pd.DataFrame, period: int) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()

    def _calculate_ema(self, series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    def _calculate_rsi(self, series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.inf)
        return 100 - (100 / (1 + rs))

    def generate_signal(self, df: pd.DataFrame) -> SignalResult:
        required_len = max(
            self.theil_window, self.ema_slow, self.rsi_period, self.atr_period,
            self.macd_slow + self.macd_signal, self.bb_period, self.volume_period
        ) + 5
        if df.empty or len(df) < required_len:
            return SignalResult(
                signal="HOLD",
                confidence=0.0,
                trend_strength=0.0,
                slope=0.0,
                details={"reason": "insufficient_data"}
            )

        close = df["close"]

        ema_fast = self._calculate_ema(close, self.ema_fast)
        ema_slow = self._calculate_ema(close, self.ema_slow)
        rsi = self._calculate_rsi(close, self.rsi_period)
        atr = self._calculate_atr(df, self.atr_period)

        macd, macd_signal, macd_hist = self._calculate_macd(close, self.macd_fast, self.macd_slow, self.macd_signal)
        bb_mid, bb_upper, bb_lower = self._calculate_bollinger(close, self.bb_period, self.bb_std)
        vol_profile = self._calculate_volume_profile(df, self.volume_period)

        slope, confidence, slope_std = self.theil.predict_trend(close)

        curr_fast = ema_fast.iloc[-1]
        curr_slow = ema_slow.iloc[-1]
        prev_fast = ema_fast.iloc[-2]
        prev_slow = ema_slow.iloc[-2]

        ma_cross_up = prev_fast <= prev_slow and curr_fast > curr_slow
        ma_cross_down = prev_fast >= prev_slow and curr_fast < curr_slow
        ma_trend_up = curr_fast > curr_slow
        ma_trend_down = curr_fast < curr_slow

        current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
        prev_rsi = rsi.iloc[-2] if not pd.isna(rsi.iloc[-2]) else 50
        rsi_rising = current_rsi > prev_rsi
        rsi_falling = current_rsi < prev_rsi

        macd_current = macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else 0
        macd_signal_current = macd_signal.iloc[-1] if not pd.isna(macd_signal.iloc[-1]) else 0
        macd_hist_current = macd_hist.iloc[-1] if not pd.isna(macd_hist.iloc[-1]) else 0
        macd_hist_prev = macd_hist.iloc[-2] if not pd.isna(macd_hist.iloc[-2]) else 0
        macd_cross_up = macd_hist_prev <= 0 and macd_hist_current > 0
        macd_cross_down = macd_hist_prev >= 0 and macd_hist_current < 0
        macd_bullish = macd_current > macd_signal_current
        macd_bearish = macd_current < macd_signal_current

        bb_mid, bb_upper, bb_lower = self._calculate_bollinger(close, self.bb_period, self.bb_std)
        bb_position = (close.iloc[-1] - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1]) if (bb_upper.iloc[-1] - bb_lower.iloc[-1]) > 0 else 0.5
        bb_squeeze = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_mid.iloc[-1] if bb_mid.iloc[-1] > 0 else 0
        bb_bullish = bb_position > 0.5 and macd_current > 0
        bb_bearish = bb_position < 0.5 and macd_current < 0

        vol_profile = self._calculate_volume_profile(df, self.volume_period)
        vol_bullish = vol_profile["vol_ratio"] > 1.2 and vol_profile["price_vs_vwap"] > 0
        vol_bearish = vol_profile["vol_ratio"] > 1.2 and vol_profile["price_vs_vwap"] < 0
        obv_bullish = vol_profile["obv"] > vol_profile["obv_sma"]

        current_atr = atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else close.iloc[-1] * 0.01
        atr_ratio = current_atr / close.iloc[-1]

        slope, confidence, slope_std = self.theil.predict_trend(close)
        trend_strength = min(abs(slope) / (close.iloc[-1] * 0.001), 1.0)

        # Weighted scoring
        w_theil = 1.5
        w_macd = 1.2
        w_bb = 1.0
        w_volume = 0.8
        w_rsi = 1.0
        w_ema = 1.0
        total_weight = w_theil + w_macd + w_bb + 0.8 + 1.0 + 1.0  # + w_volume + w_rsi + w_ema

        buy_score = 0.0
        sell_score = 0.0

        # 1. Theil-Sen trend
        if slope > 0:
            buy_score += 1.5 * confidence
        elif slope < 0:
            sell_score += 1.5 * confidence

        # 2. EMA trend
        if ma_trend_up:
            buy_score += 1.0
        elif ma_trend_down:
            sell_score += 1.0
        if ma_cross_up:
            buy_score += 0.5
        if ma_cross_down:
            sell_score += 0.5

        # 3. MACD
        if macd_bullish:
            buy_score += 1.2
        if macd_bearish:
            sell_score += 1.2
        if macd_cross_up:
            buy_score += 0.6
        if macd_cross_down:
            sell_score += 0.6

        # 4. Bollinger Bands
        if bb_bullish:
            buy_score += 1.0
        if bb_bearish:
            sell_score += 1.0
        if bb_position < 0.2:
            buy_score += 0.3
        if bb_position > 0.8:
            sell_score += 0.3

        # 5. Volume
        if vol_bullish:
            buy_score += 0.8
        if vol_bearish:
            sell_score += 0.8
        if obv_bullish:
            buy_score += 0.4

        # 6. RSI
        if current_rsi < 30:
            buy_score += 1.0
        elif current_rsi > 70:
            sell_score += 1.0
        if rsi_rising and current_rsi < 70:
            buy_score += 0.3
        if rsi_falling and current_rsi > 30:
            sell_score += 0.3

        trend_strength = min(abs(slope) / (close.iloc[-1] * 0.001), 1.0)
        trend_bonus = trend_strength * 0.5
        if slope > 0:
            buy_score += trend_bonus
        else:
            sell_score += trend_bonus

        total_weight = 6.5
        threshold = total_weight * 0.6

        self.signal_history.append(("BUY" if buy_score >= threshold else "SELL" if sell_score >= threshold else "HOLD"))
        self.signal_history = self.signal_history[-3:]

        final_signal = "HOLD"
        if buy_score >= threshold and self.signal_history.count("BUY") >= 2:
            final_signal = "BUY"
            self.last_signal = "BUY"
        elif sell_score >= threshold and self.signal_history.count("SELL") >= 2:
            final_signal = "SELL"
            self.last_signal = "SELL"
        else:
            final_signal = "HOLD"

        details = {
            "buy_score": round(buy_score, 2),
            "sell_score": round(sell_score, 2),
            "threshold": round(total_weight * 0.6, 2),
            "slope": round(slope, 6),
            "confidence": round(confidence, 3),
            "current_rsi": round(current_rsi, 1),
            "atr_ratio": round(atr_ratio, 4),
            "ema_fast": round(curr_fast, 2),
            "ema_slow": round(curr_slow, 2),
            "trend_strength": round(trend_strength, 3),
            "signal_history": self.signal_history.copy(),
            "macd": round(macd_current, 4),
            "macd_signal": round(macd_signal_current, 4),
            "macd_hist": round(macd_hist_current, 4),
            "bb_position": round(bb_position, 3),
            "vol_ratio": round(vol_profile["vol_ratio"], 2),
            "price_vs_vwap": round(vol_profile["price_vs_vwap"], 4),
        }

        return SignalResult(
            signal=final_signal,
            confidence=confidence,
            trend_strength=trend_strength,
            slope=slope,
            details=details
        )


class MACrossoverEnhanced:
    def __init__(self, fast_period: int = 9, slow_period: int = 21, use_ema: bool = True):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.use_ema = use_ema
        self.last_signal = "HOLD"

    def generate_signal(self, df: pd.DataFrame) -> str:
        if df.empty or len(df) < self.slow_period:
            return "HOLD"

        df = df.copy()
        if self.use_ema:
            df["ma_fast"] = df["close"].ewm(span=self.fast_period, adjust=False).mean()
            df["ma_slow"] = df["close"].ewm(span=self.slow_period, adjust=False).mean()
        else:
            df["ma_fast"] = df["close"].rolling(window=self.fast_period).mean()
            df["ma_slow"] = df["close"].rolling(window=self.slow_period).mean()

        prev_fast = df["ma_fast"].iloc[-2]
        prev_slow = df["ma_slow"].iloc[-2]
        curr_fast = df["ma_fast"].iloc[-1]
        curr_slow = df["ma_slow"].iloc[-1]

        # Add trend filter: only signal if price is above/below both MAs
        price = df["close"].iloc[-1]
        
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            # Golden cross - only BUY if price above slow MA
            if price > curr_slow:
                self.last_signal = "BUY"
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            # Death cross - only SELL if price below slow MA
            if price < curr_slow:
                self.last_signal = "SELL"
        else:
            self.last_signal = "HOLD"

        return self.last_signal