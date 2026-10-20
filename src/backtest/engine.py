import numpy as np
import pandas as pd


class BacktestEngine:
    """Motor de backtesting avanzado con slippage, comisiones y métricas de riesgo.

    Soporta:
      - Comisiones (maker/taker por lado)
      - Slippage (adverso en cada fill)
      - Métricas: Sharpe, Sortino, Max Drawdown, Profit Factor, Calmar
      - Walk-forward analysis
    """

    def __init__(self, config: dict = None):
        cfg = config or {}
        self.commission_pct = cfg.get("commission_pct", 0.001)  # 0.1% Binance spot
        self.slippage_pct = cfg.get("slippage_pct", 0.0005)     # 0.05%
        self.initial_balance = cfg.get("initial_balance", 10000.0)
        self.trade_quantity = cfg.get("trade_quantity", 0.001)
        self.stop_loss_pct = cfg.get("stop_loss_pct", 0.02)
        self.take_profit_pct = cfg.get("take_profit_pct", 0.03)
        self.trailing_stop_pct = cfg.get("trailing_stop_pct", 0.01)
        self.trailing_activation_pct = cfg.get("trailing_activation_pct", 0.015)
        self.time_exit_hours = cfg.get("time_exit_hours", 24)
        self.enable_trailing = cfg.get("enable_trailing", True)
        self.enable_time_exit = cfg.get("enable_time_exit", True)

    def _apply_slippage(self, price: float, side: str) -> float:
        """Slippage adverso: compras más caro, ventas más barato."""
        if side == "BUY":
            return price * (1 + self.slippage_pct)
        return price * (1 - self.slippage_pct)
    def _commission(self, price: float, qty: float) -> float:
        return price * qty * self.commission_pct

    @staticmethod
    def _elapsed_hours(entry_ts, current_ts):
        """Horas transcurridas entre dos timestamps; None si no se pueden parsear."""
        if entry_ts is None or current_ts is None:
            return None
        try:
            start = pd.to_datetime(entry_ts)
            end = pd.to_datetime(current_ts)
            delta = (end - start).total_seconds() / 3600.0
            return max(delta, 0.0)
        except Exception:
            return None

    def generate_signals(self, df: pd.DataFrame, signal_fn=None) -> pd.DataFrame:
        """Genera la columna 'signal' para el backtest.

        Si ``signal_fn`` se entrega, se aplica directamente. Si no, se usa
        ``EnhancedStrategy`` para evaluar cada ventana y etiquetar BUY/SELL/HOLD.
        Devuelve una copia del DataFrame con la columna 'signal' agregada.
        """
        if df is None or df.empty:
            return df
        df = df.copy()
        if signal_fn is not None:
            df["signal"] = signal_fn(df)
            return df

        from src.strategy.enhanced_strategy import EnhancedStrategy

        strategy = EnhancedStrategy()
        min_len = max(
            strategy.theil_window, strategy.ema_slow, strategy.rsi_period,
            strategy.atr_period, strategy.macd_slow + strategy.macd_signal,
            strategy.bb_period, strategy.volume_period,
        ) + 5
        signals = ["HOLD"] * len(df)
        for i in range(len(df)):
            if i + 1 < min_len:
                continue
            window = df.iloc[max(0, i + 1 - (min_len + 20)):i + 1]
            try:
                result = strategy.generate_signal(window)
                signals[i] = result.signal
            except Exception:
                signals[i] = "HOLD"
        df["signal"] = signals
        return df

    def run(self, df: pd.DataFrame, symbol: str = "BTCUSDT",
            signal_col: str = "signal", verbose: bool = False) -> dict:
        """Ejecuta el backtest sobre un DataFrame con columna de señales.

        df debe contener: timestamp, close y la columna de señales (BUY/SELL/HOLD).
        Si la columna de señales no existe, se genera con ``generate_signals``.
        """
        if df is None or df.empty:
            return {"error": "datos o señales insuficientes"}
        if signal_col not in df.columns:
            df = self.generate_signals(df, signal_fn=None)
        if signal_col not in df.columns:
            return {"error": "datos o señales insuficientes"}

        balance = self.initial_balance
        position = None
        entry_price = 0.0
        entry_ts = None
        qty = 0.0
        highest = 0.0
        trailing_stop = None
        trades = []
        equity_curve = []

        def open_pos(price, ts):
            nonlocal balance, position, entry_price, entry_ts, qty, highest, trailing_stop
            fill = self._apply_slippage(price, "BUY")
            cost = fill * self.trade_quantity
            fee = self._commission(fill, self.trade_quantity)
            if balance < cost + fee:
                return False
            balance -= (cost + fee)
            position = "LONG"
            entry_price = fill
            entry_ts = ts
            qty = self.trade_quantity
            highest = fill
            trailing_stop = None
            trades.append({"type": "ENTRY", "timestamp": str(ts), "price": fill, "qty": qty})
            return True

        def close_pos(price, ts, reason):
            nonlocal balance, position, entry_price, qty, highest, trailing_stop, entry_ts
            if position is None:
                return
            fill = self._apply_slippage(price, "SELL")
            proceeds = fill * qty
            fee = self._commission(fill, qty)
            balance += (proceeds - fee)
            pnl_pct = (fill - entry_price) / entry_price * 100
            trades.append({
                "type": "EXIT", "timestamp": str(ts), "price": fill, "qty": qty,
                "reason": reason, "pnl_pct": round(pnl_pct, 3),
            })
            position = None
            entry_price = 0.0
            qty = 0.0
            entry_ts = None

        for _, row in df.iterrows():
            price = float(row["close"])
            ts = row.get("timestamp", "")
            signal = row[signal_col]

            if position == "LONG":
                highest = max(highest, price)
                elapsed_hours = self._elapsed_hours(entry_ts, ts)
                # Trailing stop
                if self.enable_trailing and highest >= entry_price * (1 + self.trailing_activation_pct):
                    new_stop = highest * (1 - self.trailing_stop_pct)
                    trailing_stop = max(trailing_stop or 0, new_stop)
                # Stop loss
                if price <= entry_price * (1 - self.stop_loss_pct):
                    close_pos(price, ts, "stop_loss")
                # Take profit
                elif price >= entry_price * (1 + self.take_profit_pct):
                    close_pos(price, ts, "take_profit")
                # Trailing
                elif trailing_stop and price <= trailing_stop:
                    close_pos(price, ts, "trailing_stop")
                # Time exit
                elif (self.enable_time_exit and self.time_exit_hours
                      and elapsed_hours is not None and elapsed_hours >= self.time_exit_hours):
                    close_pos(price, ts, "time_exit")
                # Señal de venta
                elif signal == "SELL":
                    close_pos(price, ts, "signal")
            elif signal == "BUY":
                open_pos(price, ts)

            equity = balance + (qty * price if position else 0.0)
            equity_curve.append(equity)

        # Cerrar posición abierta al final
        if position == "LONG":
            close_pos(float(df["close"].iloc[-1]), df["timestamp"].iloc[-1], "end")

        return self._compute_metrics(trades, equity_curve, symbol)

    def _compute_metrics(self, trades, equity_curve, symbol):
        exits = [t for t in trades if t["type"] == "EXIT"]
        wins = [t for t in exits if t["pnl_pct"] > 0]
        losses = [t for t in exits if t["pnl_pct"] <= 0]

        equity = np.array(equity_curve, dtype=float) if equity_curve else np.array([self.initial_balance])
        final_equity = float(equity[-1]) if len(equity) else self.initial_balance
        total_return_pct = (final_equity - self.initial_balance) / self.initial_balance * 100

        returns = np.diff(equity) / equity[:-1] if len(equity) > 1 else np.array([0.0])
        returns = returns[np.isfinite(returns)]
        sharpe = self._sharpe(returns)
        sortino = self._sortino(returns)
        max_dd = self._max_drawdown(equity)

        gross_profit = sum(t["pnl_pct"] for t in wins) if wins else 0.0
        gross_loss = abs(sum(t["pnl_pct"] for t in losses)) if losses else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit else 0.0)

        calmar = (total_return_pct / max_dd) if max_dd > 0 else 0.0

        return {
            "symbol": symbol,
            "initial_balance": self.initial_balance,
            "final_balance": round(final_equity, 2),
            "total_return_pct": round(total_return_pct, 2),
            "total_trades": len(trades),
            "exits": len(exits),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(exits) * 100, 2) if exits else 0.0,
            "avg_win_pct": round(np.mean([t["pnl_pct"] for t in wins]), 3) if wins else 0.0,
            "avg_loss_pct": round(np.mean([t["pnl_pct"] for t in losses]), 3) if losses else 0.0,
            "profit_factor": round(profit_factor, 2),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "max_drawdown_pct": round(max_dd, 2),
            "calmar_ratio": round(calmar, 3),
            "commission_pct": self.commission_pct,
            "slippage_pct": self.slippage_pct,
            "equity_curve": [round(float(e), 2) for e in equity.tolist()],
        }

    @staticmethod
    def _sharpe(returns, periods_per_year=365):
        if len(returns) < 2 or np.std(returns) == 0:
            return 0.0
        return float(np.mean(returns) / np.std(returns) * np.sqrt(periods_per_year))

    @staticmethod
    def _sortino(returns, periods_per_year=365):
        downside = returns[returns < 0]
        if len(returns) < 2 or len(downside) == 0 or np.std(downside) == 0:
            return 0.0
        return float(np.mean(returns) / np.std(downside) * np.sqrt(periods_per_year))

    @staticmethod
    def _max_drawdown(equity):
        if len(equity) < 2:
            return 0.0
        peak = np.maximum.accumulate(equity)
        dd = (equity - peak) / peak
        return float(abs(dd.min()) * 100)


def walk_forward_analysis(df: pd.DataFrame, engine_factory, n_splits: int = 4,
                          signal_fn=None, symbol: str = "BTCUSDT") -> dict:
    """Walk-forward: divide los datos en ventanas y valida out-of-sample.

    df: DataFrame completo con features.
    engine_factory: callable() -> BacktestEngine
    signal_fn: callable(train_df, test_df) -> test_df con columna 'signal'
    """
    if df is None or df.empty or n_splits < 2:
        return {"error": "datos insuficientes"}

    fold_size = len(df) // n_splits
    results = []

    for i in range(n_splits):
        start = i * fold_size
        end = start + fold_size if i < n_splits - 1 else len(df)
        split = start + int(fold_size * 0.7)
        train = df.iloc[start:split]
        test = df.iloc[split:end].copy()
        if test.empty:
            continue

        if signal_fn:
            test = signal_fn(train, test)
        else:
            # Señal trivial: momentum (close > close previo)
            test["signal"] = np.where(test["close"] > test["close"].shift(1), "BUY", "SELL")
            test["signal"] = test["signal"].fillna("HOLD")

        engine = engine_factory()
        res = engine.run(test, symbol=symbol)
        results.append({
            "fold": i + 1,
            "test_start": str(test["timestamp"].iloc[0]),
            "test_end": str(test["timestamp"].iloc[-1]),
            "return_pct": res.get("total_return_pct", 0.0),
            "sharpe": res.get("sharpe_ratio", 0.0),
            "max_dd_pct": res.get("max_drawdown_pct", 0.0),
            "win_rate": res.get("win_rate", 0.0),
            "trades": res.get("exits", 0),
        })

    if not results:
        return {"error": "sin folds válidos"}

    avg_return = np.mean([r["return_pct"] for r in results])
    avg_sharpe = np.mean([r["sharpe"] for r in results])
    consistency = len([r for r in results if r["return_pct"] > 0]) / len(results) * 100

    return {
        "symbol": symbol,
        "folds": results,
        "avg_return_pct": round(float(avg_return), 2),
        "avg_sharpe": round(float(avg_sharpe), 3),
        "consistency_pct": round(consistency, 1),
        "n_splits": n_splits,
    }