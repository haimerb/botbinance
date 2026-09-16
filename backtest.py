#!/usr/bin/env python
"""
Backtest script para probar la EnhancedStrategy con datos históricos de Binance.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.strategy.enhanced_strategy import EnhancedStrategy, MACrossoverEnhanced
from src.models.trainer import add_technical_features
from src.data.binance_client import BinanceDataClient
from src.config import USE_TESTNET


def run_backtest(
    symbol: str = "BTCUSDT",
    interval: str = "1h",
    days: int = 90,
    initial_balance: float = 10000.0,
    trade_quantity: float = 0.001,
    stop_loss_pct: float = 0.02,
    take_profit_pct: float = 0.03,
    trailing_stop_pct: float = 0.01,
    trailing_activation_pct: float = 0.015,
    time_exit_hours: int = 24,
    enable_trailing: bool = True,
    enable_time_exit: bool = True,
    enable_partial_tp: bool = True,
    partial_tp_levels: list = None,
    commission_pct: float = 0.001,
    verbose: bool = True,
) -> dict:
    """
    Ejecuta backtest de la EnhancedStrategy con datos históricos reales.
    """
    if partial_tp_levels is None:
        partial_tp_levels = [
            (0.015, 0.3),
            (0.03, 0.3),
            (0.05, 0.4),
        ]

    print(f"\n{'='*60}")
    print(f"BACKTEST: {symbol} {interval} - {days} días")
    print(f"{'='*60}")
    print(f"Balance inicial: ${initial_balance:,.2f}")
    print(f"Cantidad por trade: {trade_quantity}")
    print(f"Stop Loss: {stop_loss_pct*100:.1f}%")
    print(f"Take Profit: {take_profit_pct*100:.1f}%")
    print(f"Trailing Stop: {trailing_stop_pct*100:.1f}% (activación: {trailing_activation_pct*100:.1f}%)")
    print(f"Time Exit: {time_exit_hours}h")
    print(f"Comisión: {commission_pct*100:.2f}%")
    print(f"{'='*60}\n")

    # Fetch historical data
    print("Descargando datos históricos...")
    try:
        client = BinanceDataClient()
        # Calculate limit based on days and interval
        if interval == "1h":
            limit = days * 24
        elif interval == "15m":
            limit = days * 96
        elif interval == "30m":
            limit = days * 48
        elif interval == "4h":
            limit = days * 6
        elif interval == "1d":
            limit = days
        else:
            limit = days * 24
        
        df = client.fetch_klines(symbol, interval, limit=limit, use_real_api=True)
        if df.empty:
            print("  Fallback a testnet...")
            df = client.fetch_klines(symbol, interval, limit=limit, use_real_api=False)
        if df.empty:
            print("ERROR: No se pudieron obtener datos históricos")
            return {}
        print(f"Datos cargados: {len(df)} velas desde {df['timestamp'].iloc[0]} hasta {df['timestamp'].iloc[-1]}")
    except Exception as e:
        print(f"ERROR descargando datos: {e}")
        return {}

    # Add technical features
    df = add_technical_features(df)
    df = df.dropna()

    # Initialize strategies
    enhanced = EnhancedStrategy(
        theil_window=20,
        ema_fast=9,
        ema_slow=21,
        rsi_period=14,
        atr_period=14,
    )
    ma_strategy = MACrossoverEnhanced(fast_period=9, slow_period=21)

    # Simulation state
    balance = initial_balance
    position = None
    entry_price = 0.0
    entry_time = None
    qty = 0.0
    highest_price = 0.0
    lowest_price = 0.0
    trailing_stop_price = None
    partial_tp_levels_executed = []
    trades = []
    daily_returns = []

    def open_pos(price, timestamp):
        nonlocal position, entry_price, entry_time, qty, highest_price, lowest_price, trailing_stop_price, balance
        cost = price * trade_quantity
        if balance < cost:
            return False
        balance -= cost
        position = "LONG"
        entry_price = price
        entry_time = timestamp
        qty = trade_quantity
        highest_price = price
        lowest_price = price
        trailing_stop_price = None
        trades.append({
            "type": "ENTRY",
            "timestamp": timestamp,
            "price": price,
            "qty": qty,
            "balance": balance,
        })
        if verbose:
            print(f"[{timestamp}] ENTRY LONG @ ${price:,.2f} | Balance: ${balance:,.2f}")
        return True

    def close_pos(price, timestamp, reason, exit_qty=None):
        nonlocal position, entry_price, entry_time, qty, highest_price, lowest_price, trailing_stop_price, balance
        if position is None:
            return
        if exit_qty is None:
            exit_qty = qty
        pnl = (price - entry_price) * exit_qty
        commission = price * exit_qty * commission_pct
        net_pnl = pnl - commission
        balance += price * exit_qty - commission
        pnl_pct = (price - entry_price) / entry_price * 100
        trades.append({
            "type": "EXIT",
            "timestamp": timestamp,
            "price": price,
            "qty": exit_qty,
            "pnl": net_pnl,
            "pnl_pct": pnl_pct,
            "reason": reason,
            "balance": balance,
        })
        if verbose:
            print(f"[{timestamp}] EXIT {reason} @ ${price:,.2f} | PnL: ${net_pnl:,.2f} ({pnl_pct:+.2f}%) | Balance: ${balance:,.2f}")
        if exit_qty >= qty:
            position = None
            entry_price = 0.0
            entry_time = None
            qty = 0.0
            highest_price = 0.0
            lowest_price = 0.0
        else:
            qty -= exit_qty
        trailing_stop_price = None

    # Run simulation
    print("\nEjecutando simulación...\n")
    
    # Pre-compute signals for all candles to avoid recalculating
    print("Pre-computando señales...")
    ma_signals = []
    enhanced_signals = []
    consensus_signals = []
    
    for i in range(len(df)):
        ma_signal = ma_strategy.generate_signal(df.iloc[:i+1])
        enhanced_result = enhanced.generate_signal(df.iloc[:i+1])
        
        # Consensus: Enhanced as primary, MA as filter
        # BUY if Enhanced says BUY and MA is not SELL
        # SELL if Enhanced says SELL and MA is not BUY
        # Otherwise HOLD
        if enhanced_result.signal == "BUY" and ma_signal != "SELL":
            consensus = "BUY"
        elif enhanced_result.signal == "SELL" and ma_signal != "BUY":
            consensus = "SELL"
        else:
            consensus = "HOLD"
        
        ma_signals.append(ma_signal)
        enhanced_signals.append(enhanced_result)
        consensus_signals.append(consensus)
    
    print("Simulación en curso...")
    for i in range(len(df)):
        row = df.iloc[i]
        timestamp = row["timestamp"]
        price = row["close"]

        # Use pre-computed signals
        ma_signal = ma_signals[i]
        enhanced_result = enhanced_signals[i]
        consensus = consensus_signals[i]

        # Check exits if position open
        if position == "LONG":
            highest_price = max(highest_price, price)
            lowest_price = min(lowest_price, price)

            # Stop Loss
            loss_pct = (entry_price - price) / entry_price
            if loss_pct >= stop_loss_pct:
                close_pos(price, timestamp, "STOP_LOSS")
                continue

            # Trailing Stop
            if enable_trailing:
                gain_pct = (price - entry_price) / entry_price
                if gain_pct >= trailing_activation_pct:
                    new_trailing = price * (1 - trailing_stop_pct)
                    if trailing_stop_price is None or new_trailing > trailing_stop_price:
                        trailing_stop_price = new_trailing
                    if trailing_stop_price and price <= trailing_stop_price:
                        close_pos(price, timestamp, "TRAILING_STOP")
                        continue

            # Time Exit
            if enable_time_exit and time_exit_hours > 0:
                elapsed_hours = (timestamp - entry_time).total_seconds() / 3600
                if elapsed_hours >= time_exit_hours:
                    close_pos(price, timestamp, "TIME_EXIT")
                    continue

            # Take Profit
            gain_pct = (price - entry_price) / entry_price
            if gain_pct >= take_profit_pct:
                close_pos(price, timestamp, "TAKE_PROFIT")
                continue

        # Check entry
        if position is None and consensus == "BUY":
            open_pos(price, timestamp)

    # Close any remaining position at end
    if position == "LONG":
        close_pos(df.iloc[-1]["close"], df.iloc[-1]["timestamp"], "END_OF_DATA")

    # Calculate metrics
    exits = [t for t in trades if t["type"] == "EXIT"]
    wins = [t for t in exits if t["pnl"] > 0]
    losses = [t for t in exits if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in exits)
    total_pnl_pct = (balance - initial_balance) / initial_balance * 100
    win_rate = len(wins) / len(exits) * 100 if exits else 0
    avg_win = np.mean([t["pnl_pct"] for t in wins]) if wins else 0
    avg_loss = np.mean([t["pnl_pct"] for t in losses]) if losses else 0
    profit_factor = abs(sum(t["pnl"] for t in wins) / sum(t["pnl"] for t in losses)) if losses else float('inf')
    max_drawdown = 0.0
    peak = initial_balance
    for t in trades:
        if t["type"] == "EXIT":
            peak = max(peak, t["balance"])
            dd = (peak - t["balance"]) / peak * 100
            max_drawdown = max(max_drawdown, dd)

    result = {
        "symbol": symbol,
        "interval": interval,
        "days": days,
        "initial_balance": initial_balance,
        "final_balance": balance,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "total_trades": len(exits),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": win_rate,
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "profit_factor": profit_factor,
        "max_drawdown_pct": max_drawdown,
        "trades": trades,
    }

    if verbose:
        print(f"\n{'='*60}")
        print("RESULTADOS DEL BACKTEST")
        print(f"{'='*60}")
        print(f"Balance inicial:    ${initial_balance:,.2f}")
        print(f"Balance final:      ${balance:,.2f}")
        print(f"PnL total:          ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)")
        print(f"Total trades:       {len(exits)}")
        print(f"  Wins:             {len(wins)}")
        print(f"  Losses:           {len(losses)}")
        print(f"Win Rate:           {win_rate:.1f}%")
        print(f"Avg Win:            {avg_win:+.2f}%")
        print(f"Avg Loss:           {avg_loss:+.2f}%")
        print(f"Profit Factor:      {profit_factor:.2f}")
        print(f"Max Drawdown:       {max_drawdown:.2f}%")
        print(f"{'='*60}\n")

    return result


def main():
    parser = argparse.ArgumentParser(description="Backtest EnhancedStrategy")
    parser.add_argument("--symbol", default="BTCUSDT", help="Símbolo (ej: BTCUSDT)")
    parser.add_argument("--interval", default="1h", help="Intervalo (15m, 30m, 1h, 4h, 1d)")
    parser.add_argument("--days", type=int, default=90, help="Días de datos históricos")
    parser.add_argument("--balance", type=float, default=10000.0, help="Balance inicial")
    parser.add_argument("--qty", type=float, default=0.001, help="Cantidad por trade")
    parser.add_argument("--sl", type=float, default=2.0, help="Stop Loss %")
    parser.add_argument("--tp", type=float, default=3.0, help="Take Profit %")
    parser.add_argument("--trailing", type=float, default=1.0, help="Trailing Stop %")
    parser.add_argument("--trailing-act", type=float, default=1.5, help="Trailing Activation %")
    parser.add_argument("--time-exit", type=int, default=24, help="Time Exit (horas, 0=desactivado)")
    parser.add_argument("--no-trailing", action="store_true", help="Desactivar trailing stop")
    parser.add_argument("--no-time-exit", action="store_true", help="Desactivar time exit")
    parser.add_argument("--no-partial", action="store_true", help="Desactivar partial TP")
    parser.add_argument("--commission", type=float, default=0.1, help="Comisión %")
    parser.add_argument("--quiet", action="store_true", help="Solo mostrar resumen")
    parser.add_argument("--output", help="Archivo JSON para guardar resultados")

    args = parser.parse_args()

    result = run_backtest(
        symbol=args.symbol,
        interval=args.interval,
        days=args.days,
        initial_balance=args.balance,
        trade_quantity=args.qty,
        stop_loss_pct=args.sl / 100,
        take_profit_pct=args.tp / 100,
        trailing_stop_pct=args.trailing / 100,
        trailing_activation_pct=args.trailing_act / 100,
        time_exit_hours=args.time_exit,
        enable_trailing=not args.no_trailing,
        enable_time_exit=not args.no_time_exit,
        enable_partial_tp=not args.no_partial,
        commission_pct=args.commission / 100,
        verbose=not args.quiet,
    )

    if args.output:
        with open(args.output, "w") as f:
            # Convert datetime to string for JSON serialization
            def serialize(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                if isinstance(obj, (np.integer, np.floating)):
                    return float(obj)
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                return str(obj)
            
            json.dump(result, f, indent=2, default=serialize)
            print(f"\nResultados guardados en {args.output}")

    return 0 if result.get("total_pnl_pct", 0) > 0 else 1


if __name__ == "__main__":
    sys.exit(main())