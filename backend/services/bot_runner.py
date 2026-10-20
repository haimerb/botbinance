import copy
import threading
import time
import random
import math
import psutil
from datetime import datetime
from typing import Optional

from src.config import DEFAULT_SYMBOLS, INTERVAL, TRADE_QUANTITY, BALANCE_ALLOCATION_PCT
from src.data.binance_client import BinanceDataClient
from src.strategy.ml_strategy import MLStrategy
from src.strategy.enhanced_strategy import EnhancedStrategy, MACrossoverEnhanced
from src.strategy.sentiment import get_analyzer
from src.execution.trade_executor import TradeExecutor
from src.risk.risk_manager import RiskManager, ExitReason
from backend.services.database import add_trade, get_user_by_id, get_user_by_id_with_keys
from backend.services.user_config import load_user_config
from backend.services.metrics import (
    update_bot_status,
    update_pnl,
    update_circuit_breaker,
    record_trade,
    record_signal,
    record_ml_prediction,
    record_ml_error,
    set_binance_connections,
    update_system_metrics,
    update_risk_metrics,
)


class BotRunner:
    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self.running = False
        self.thread = None
        self.user_id = None
        self.config = {}
        self._lock = threading.Lock()
        self.state = {
            "status": "stopped",
            "mock_mode": mock_mode,
            "symbols": list(DEFAULT_SYMBOLS),
            "current_prices": {},
            "positions": {},
            "signals": {},
            "strategy_details": {},
            "balance": 10000.0,
            "pnl": 0.0,
            "total_pnl": 0.0,
            "total_balance": 10000.0,
            "model_accuracy": 38.78,
            "last_update": None,
            "last_trade_id": 0,
            "daily_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "circuit_breaker_triggered": False,
            "max_daily_loss_pct": 5.0,
            "max_total_loss_pct": 10.0,
        }
        self.mock_prices = {}
        self.mock_phases = {}
        self._risk_managers = {}
        self._enhanced_strategies = {}
        self._ma_strategies = {}
        self._ml_strategies = {}
        self._portfolio_manager = None
        self._symbol_weights = {}
        self._price_history = {}

    def set_user(self, user_id: int):
        with self._lock:
            self.user_id = user_id
            if user_id:
                self.config = load_user_config(user_id)
                self.state["symbols"] = list(self.config.get("symbols", DEFAULT_SYMBOLS))
                alloc_pct = self.config.get("balance_allocation_pct", BALANCE_ALLOCATION_PCT)
                total_balance = 10000.0
                self.state["total_balance"] = total_balance
                self.state["balance"] = total_balance * (alloc_pct / 100.0)
                self.state["initial_balance"] = self.state["balance"]
                self.state["max_daily_loss_pct"] = self.config.get("max_daily_loss_pct", 5.0)
                self.state["max_total_loss_pct"] = self.config.get("max_total_loss_pct", 10.0)
                symbols = self.state["symbols"]
                for s in symbols:
                    if s not in self.state["current_prices"]:
                        self.state["current_prices"][s] = 0.0
                        self.state["positions"][s] = None
                        self.state["signals"][s] = {"ma": "HOLD", "ml": "HOLD", "enhanced": "HOLD", "consensus": "HOLD"}
                        self.state["strategy_details"][s] = {}
                        self.mock_prices[s] = 65000.0 if "BTC" in s else 3500.0 if "ETH" in s else 150.0
                        self.mock_phases[s] = random.random() * 6.28
                self._risk_managers.clear()
                self._enhanced_strategies.clear()
                self._ma_strategies.clear()
                self._ml_strategies.clear()
                from src.risk.portfolio_manager import PortfolioManager
                mode = self.config.get("portfolio_allocation_mode", "equal")
                self._portfolio_manager = PortfolioManager(mode=mode)
                self._symbol_weights = {}
                self._price_history = {}
        update_bot_status("stopped")

    def _mock_tick(self, symbol: str) -> float:
        phase = self.mock_phases.get(symbol, 0.0)
        price = self.mock_prices.get(symbol, 65000.0)
        phase += 0.1 + random.gauss(0, 0.03)
        noise = random.gauss(0, 50)
        trend = math.sin(phase) * 200
        price += noise + trend * 0.02
        price = max(1000, min(200000, price))
        self.mock_phases[symbol] = phase
        self.mock_prices[symbol] = price
        return round(price, 2)

    def _mock_signal(self):
        ma = random.choices(["BUY", "SELL", "HOLD"], weights=[0.15, 0.1, 0.75])[0]
        ml = random.choices(["BUY", "SELL", "HOLD"], weights=[0.2, 0.15, 0.65])[0]
        enhanced = random.choices(["BUY", "SELL", "HOLD"], weights=[0.18, 0.12, 0.70])[0]
        consensus = ma if ma == ml and ma != "HOLD" else "HOLD"
        return ma, ml, enhanced, consensus

    def _refresh_pnl_and_balance(self):
        unrealized = 0.0
        total_pos_value = 0.0
        for sym, pos in self.state["positions"].items():
            if not pos:
                continue
            price = self.state["current_prices"].get(sym, pos.get("entry", 0))
            qty = pos.get("qty", 0)
            unrealized += (price - pos.get("entry", 0)) * qty
            total_pos_value += price * qty
        self.state["unrealized_pnl"] = unrealized
        self.state["total_pnl"] = self.state["pnl"] + unrealized
        self.state["total_balance"] = self.state["balance"] + total_pos_value

    def _mock_trade_logic(self, symbol: str, price: float, signal: str, qty: float):
        pos = self.state["positions"].get(symbol)
        rm = self._risk_managers.get(symbol)

        if signal == "BUY" and not pos:
            cost = price * qty
            if self.state["balance"] < cost:
                return
            self.state["balance"] -= cost
            self.state["positions"][symbol] = {
                "side": "BUY", "entry": price, "qty": qty,
                "time": datetime.now().isoformat(),
            }
            if rm:
                rm.open_position(price, qty)
            record_trade(symbol, "BUY", "filled")
            if self.user_id:
                tid = add_trade(self.user_id, "BUY", price, qty, "entry", symbol=symbol)
                self.state["last_trade_id"] = tid

        elif signal == "SELL" and pos:
            entry = pos.get("entry", price)
            pnl_pct = (price - entry) / entry * 100
            self.state["balance"] += price * qty
            self.state["pnl"] += (price - entry) * qty
            self.state["daily_pnl"] += (price - entry) * qty
            self.state["positions"][symbol] = None
            if rm:
                rm.close_position(ExitReason.SIGNAL_REVERSAL)
            record_trade(symbol, "SELL", "filled")
            if self.user_id:
                tid = add_trade(self.user_id, "SELL", price, qty, "exit", round(pnl_pct, 2), symbol=symbol)
                self.state["last_trade_id"] = tid

    def _check_circuit_breakers(self) -> bool:
        if self.state["circuit_breaker_triggered"]:
            return True
        
        initial_balance = self.state.get("initial_balance", 10000.0)
        max_daily_loss = self.state.get("max_daily_loss_pct", 5.0) / 100.0
        max_total_loss = self.state.get("max_total_loss_pct", 10.0) / 100.0
        
        daily_loss_pct = abs(self.state["daily_pnl"]) / initial_balance if self.state["daily_pnl"] < 0 else 0
        total_loss_pct = abs(self.state["pnl"]) / initial_balance if self.state["pnl"] < 0 else 0
        
        if daily_loss_pct >= max_daily_loss:
            self.state["circuit_breaker_triggered"] = True
            self.state["status"] = f"circuit_breaker: max daily loss ({max_daily_loss*100:.1f}%) exceeded"
            self._notify_circuit_breaker("max daily loss", daily_loss_pct * 100)
            return True
        
        if total_loss_pct >= max_total_loss:
            self.state["circuit_breaker_triggered"] = True
            self.state["status"] = f"circuit_breaker: max total loss ({max_total_loss*100:.1f}%) exceeded"
            self._notify_circuit_breaker("max total loss", total_loss_pct * 100)
            return True
        
        return False

    def _notify_circuit_breaker(self, reason: str, loss_pct: float):
        email = f"user_{self.user_id}"
        try:
            from backend.workers.tasks import send_circuit_breaker_alert
            send_circuit_breaker_alert.delay(email, reason, round(loss_pct, 2))
        except Exception:
            try:
                from backend.services.notifications import notify_circuit_breaker
                notify_circuit_breaker(email, reason, round(loss_pct, 2))
            except Exception:
                pass

    def _notify_trade(self, symbol: str, side: str, price: float, qty: float, pnl_pct=None):
        email = f"user_{self.user_id}"
        try:
            from backend.workers.tasks import send_trade_notification
            send_trade_notification.delay(email, symbol, side, price, qty, pnl_pct)
        except Exception:
            try:
                from backend.services.notifications import notify_trade
                notify_trade(email, symbol, side, price, qty, pnl_pct)
            except Exception:
                pass

    def _notify_error(self, error: str):
        try:
            from backend.services.notifications import notify_bot_error
            notify_bot_error(f"user_{self.user_id}", error)
        except Exception:
            pass

    def _portfolio_qty(self, symbol: str, price: float, confidences: dict, base_qty: float) -> float:
        """Cantidad a operar según el modo de asignación de cartera.

        La confianza del modelo escala la cantidad base; el peso de cartera del
        símbolo (volatilidad/confianza) modula la exposición relativa.
        """
        if not self._portfolio_manager or price <= 0:
            return base_qty

        history = self._price_history.get(symbol, [])
        from src.risk.portfolio_manager import PortfolioManager
        volatility = PortfolioManager.compute_volatility(history) if len(history) >= 2 else 0.02

        symbols = list(self.state["symbols"])
        volatilities = {}
        for s in symbols:
            hist = self._price_history.get(s, [])
            volatilities[s] = PortfolioManager.compute_volatility(hist) if len(hist) >= 2 else 0.02

        mode = self._portfolio_manager.mode
        if mode == "equal":
            weight = 1.0 / len(symbols) if symbols else 1.0
        else:
            weights = self._portfolio_manager.compute_weights(symbols, volatilities, confidences)
            self._symbol_weights = weights
            weight = weights.get(symbol, 1.0 / len(symbols) if symbols else 1.0)

        conf = max(float(confidences.get(symbol, 1.0)), 0.1)
        scale = weight * len(symbols) * conf if mode != "equal" else 1.0
        return round(base_qty * max(scale, 0.1), 8)

    def _run_mock(self):
        with self._lock:
            self.state["status"] = "running"
            self.state["circuit_breaker_triggered"] = False
        update_bot_status("running")
        set_binance_connections(True, True)
        while self.running:
            with self._lock:
                symbols = list(self.state["symbols"])
            if not symbols:
                time.sleep(2)
                continue
            with self._lock:
                if self._check_circuit_breakers():
                    update_bot_status("circuit_breaker")
                    self.running = False
                    break
                for sym in symbols:
                    price = self._mock_tick(sym)
                    ma_sig, ml_sig, enh_sig, consensus = self._mock_signal()
                    self.state["current_prices"][sym] = price
                    self.state["signals"][sym] = {
                        "ma": ma_sig, "ml": ml_sig, "enhanced": enh_sig, "consensus": consensus
                    }
                    record_signal(sym, ma_sig)
                    record_signal(sym, ml_sig)
                    record_signal(sym, enh_sig)
                    record_ml_prediction(sym, ml_sig)
                    qty = self.config.get("trade_quantity", TRADE_QUANTITY)
                    self._mock_trade_logic(sym, price, consensus, qty)

                    rm = self._risk_managers.get(sym)
                    if rm and rm.has_position():
                        exits = rm.check_all_exits(price)
                        for reason, msg in exits:
                            if reason in (ExitReason.STOP_LOSS, ExitReason.TRAILING_STOP,
                                          ExitReason.TAKE_PROFIT, ExitReason.TIME_EXIT):
                                pos = self.state["positions"].get(sym)
                                if pos:
                                    exit_qty = pos.get("qty", qty)
                                    self.state["balance"] += price * exit_qty
                                    pnl_pct = (price - pos.get("entry", price)) / pos.get("entry", price) * 100
                                    self.state["pnl"] += (price - pos.get("entry", price)) * exit_qty
                                    self.state["daily_pnl"] += (price - pos.get("entry", price)) * exit_qty
                                    self.state["positions"][sym] = None
                                    rm.close_position(reason)
                                    if self.user_id:
                                        tid = add_trade(self.user_id, "SELL", price, exit_qty, reason.value, round(pnl_pct, 2), symbol=sym)
                                        self.state["last_trade_id"] = tid

                            elif reason == ExitReason.PARTIAL_TP:
                                pass

                self._refresh_pnl_and_balance()
                pnl_by_symbol = {}
                for sym, pos in self.state["positions"].items():
                    if pos:
                        entry = pos.get("entry", 0)
                        qty = pos.get("qty", 0)
                        current = self.state["current_prices"].get(sym, entry)
                        pnl_by_symbol[sym] = (current - entry) * qty
                update_pnl(self.state["total_pnl"], pnl_by_symbol)
                update_circuit_breaker(
                    (abs(self.state["daily_pnl"]) / self.state.get("initial_balance", 10000.0)) * 100 if self.state["daily_pnl"] < 0 else 0,
                    (abs(self.state["pnl"]) / self.state.get("initial_balance", 10000.0)) * 100 if self.state["pnl"] < 0 else 0
                )
                update_system_metrics(psutil.cpu_percent(), psutil.virtual_memory().percent)
                self.state["last_update"] = datetime.now().isoformat()
            time.sleep(2)
        update_bot_status("stopped")
        set_binance_connections(False, False)

    def _run_live(self):
        try:
            user = get_user_by_id_with_keys(self.user_id) if self.user_id else None
            if not user or not user.binance_api_key or not user.binance_api_secret:
                self.state["status"] = "error: API keys no configuradas"
                update_bot_status("error")
                return

            api_key = user.binance_api_key
            api_secret = user.binance_api_secret

            cfg = self.config
            data_client = BinanceDataClient(api_key=api_key, api_secret=api_secret)

            for sym in self.state["symbols"]:
                if sym not in self._ma_strategies:
                    self._ma_strategies[sym] = MACrossoverEnhanced(
                        fast_period=cfg.get("ma_fast_period", 9),
                        slow_period=cfg.get("ma_slow_period", 21),
                    )
                if sym not in self._ml_strategies:
                    self._ml_strategies[sym] = MLStrategy(
                        confidence_threshold=cfg.get("ml_confidence_threshold", 0.55),
                    )
                if sym not in self._enhanced_strategies:
                    self._enhanced_strategies[sym] = EnhancedStrategy(
                        theil_window=cfg.get("theil_window", 20),
                        ema_fast=cfg.get("ema_fast", 9),
                        ema_slow=cfg.get("ema_slow", 21),
                        rsi_period=cfg.get("rsi_period", 14),
                        atr_period=cfg.get("atr_period", 14),
                    )

            executor = TradeExecutor(api_key=api_key, api_secret=api_secret)
            set_binance_connections(True, True)

            with self._lock:
                self.state["status"] = "running"
                self.state["circuit_breaker_triggered"] = False
            update_bot_status("running")

            while self.running:
                symbols = list(self.state["symbols"])
                if not symbols:
                    time.sleep(10)
                    continue

                with self._lock:
                    if self._check_circuit_breakers():
                        update_bot_status("circuit_breaker")
                        self.running = False
                        break

                for sym in symbols:
                    df = data_client.fetch_klines(sym, cfg.get("interval", "1h"))
                    if df.empty:
                        continue

                    ma_signal = self._ma_strategies[sym].generate_signal(df)
                    ml_signal = self._ml_strategies[sym].generate_signal(df)
                    enhanced_result = self._enhanced_strategies[sym].generate_signal(df)

                    record_signal(sym, ma_signal)
                    record_signal(sym, ml_signal)
                    record_signal(sym, enhanced_result.signal)
                    record_ml_prediction(sym, ml_signal)

                    consensus_signals = [ma_signal, ml_signal, enhanced_result.signal]
                    buy_votes = consensus_signals.count("BUY")
                    sell_votes = consensus_signals.count("SELL")
                    if buy_votes >= 2:
                        consensus = "BUY"
                    elif sell_votes >= 2:
                        consensus = "SELL"
                    else:
                        consensus = "HOLD"

                    sentiment_info = {}
                    if cfg.get("sentiment_enabled", True):
                        try:
                            analyzer = get_analyzer()
                            adjusted, reason = analyzer.filter_signal(sym, consensus)
                            sentiment_info = analyzer.get_sentiment(sym)
                            if adjusted != consensus:
                                sentiment_info["filtered_from"] = consensus
                                sentiment_info["filter_reason"] = reason
                                consensus = adjusted
                        except Exception:
                            pass

                    price = executor.get_symbol_price(sym)
                    if price == 0.0:
                        continue

                    with self._lock:
                        self.state["current_prices"][sym] = price
                        self.state["signals"][sym] = {
                            "ma": ma_signal,
                            "ml": ml_signal,
                            "enhanced": enhanced_result.signal,
                            "consensus": consensus,
                        }
                        self.state["strategy_details"][sym] = enhanced_result.details
                        if sentiment_info:
                            self.state["strategy_details"][sym] = {
                                **enhanced_result.details,
                                "sentiment": sentiment_info,
                            }
                        hist = self._price_history.setdefault(sym, [])
                        hist.append(price)
                        if len(hist) > 60:
                            del hist[:-60]

                    rm = self._risk_managers.get(sym)
                    if not rm:
                        base_sl = cfg.get("stop_loss_pct", 0.02)
                        base_tp = cfg.get("take_profit_pct", 0.03)
                        if cfg.get("ai_stop_loss_enabled", False):
                            atr = df["atr_ratio"].iloc[-1] if "atr_ratio" in df.columns else 0.02
                            base_sl = min(max(atr * 1.5, 0.01), 0.05)
                            base_tp = min(max(atr * 3, 0.02), 0.08)

                        rm = RiskManager(
                            stop_loss_pct=base_sl,
                            take_profit_pct=base_tp,
                            max_position_size=cfg.get("max_position_size", 0.01),
                            trailing_stop_pct=cfg.get("trailing_stop_pct", 0.01),
                            trailing_activation_pct=cfg.get("trailing_activation_pct", 0.015),
                            time_exit_hours=cfg.get("time_exit_hours", 24),
                            enable_trailing=cfg.get("enable_trailing", True),
                            enable_time_exit=cfg.get("enable_time_exit", True),
                            enable_partial_tp=cfg.get("enable_partial_tp", True),
                        )
                        self._risk_managers[sym] = rm
                    elif cfg.get("ai_stop_loss_enabled", False):
                        atr = df["atr_ratio"].iloc[-1] if "atr_ratio" in df.columns else 0.02
                        sl = min(max(atr * 1.5, 0.01), 0.05)
                        tp = min(max(atr * 3, 0.02), 0.08)
                        rm.set_dynamic_levels(sl, tp)

                    base_qty = cfg.get("trade_quantity", TRADE_QUANTITY)
                    confidences = {}
                    for s in symbols:
                        det = self.state["strategy_details"].get(s, {})
                        conf = det.get("confidence")
                        signals = self.state["signals"].get(s, {})
                        if conf is None:
                            conf = 0.6 if signals.get("consensus") == "BUY" else 0.4
                        confidences[s] = float(conf)
                    qty = self._portfolio_qty(sym, price, confidences, base_qty)

                    if rm.has_position():
                        exits = rm.check_all_exits(price)
                        pos = self.state["positions"].get(sym)

                        for reason, msg in exits:
                            if reason in (ExitReason.STOP_LOSS, ExitReason.TRAILING_STOP,
                                          ExitReason.TAKE_PROFIT, ExitReason.TIME_EXIT):
                                if pos:
                                    exit_qty = pos.get("qty", qty)
                                    executor.execute_order("SELL", exit_qty, sym)
                                    pnl_pct = (price - pos.get("entry", price)) / pos.get("entry", price) * 100
                                    self.state["balance"] += price * exit_qty
                                    self.state["pnl"] += (price - pos.get("entry", price)) * exit_qty
                                    self.state["daily_pnl"] += (price - pos.get("entry", price)) * exit_qty
                                    with self._lock:
                                        self.state["positions"][sym] = None
                                    rm.close_position(reason)
                                    if self.user_id:
                                        tid = add_trade(self.user_id, "SELL", price, exit_qty, reason.value, round(pnl_pct, 2), symbol=sym)
                                        self.state["last_trade_id"] = tid

                            elif reason == ExitReason.PARTIAL_TP:
                                pass

                    elif consensus == "BUY":
                        if rm.open_position(price, qty):
                            executor.execute_order("BUY", qty, sym)
                            record_trade(sym, "BUY", "filled")
                            with self._lock:
                                self.state["positions"][sym] = {
                                    "side": "BUY", "entry": price, "qty": qty,
                                    "time": datetime.now().isoformat(),
                                }
                            if self.user_id:
                                tid = add_trade(self.user_id, "BUY", price, qty, "entry", symbol=sym)
                                self.state["last_trade_id"] = tid
                            self._notify_trade(sym, "BUY", price, qty, None)

                    elif consensus == "SELL" and rm.has_position():
                        pos = self.state["positions"].get(sym)
                        if pos:
                            executor.execute_order("SELL", qty, sym)
                            record_trade(sym, "SELL", "filled")
                            pnl_pct = (price - pos.get("entry", price)) / pos.get("entry", price) * 100
                            self.state["balance"] += price * qty
                            self.state["pnl"] += (price - pos.get("entry", price)) * qty
                            self.state["daily_pnl"] += (price - pos.get("entry", price)) * qty
                            with self._lock:
                                self.state["positions"][sym] = None
                            rm.close_position(ExitReason.SIGNAL_REVERSAL)
                            if self.user_id:
                                tid = add_trade(self.user_id, "SELL", price, qty, "exit", round(pnl_pct, 2), symbol=sym)
                                self.state["last_trade_id"] = tid
                            self._notify_trade(sym, "SELL", price, qty, round(pnl_pct, 2))

                    with self._lock:
                        self._refresh_pnl_and_balance()
                        pnl_by_symbol = {}
                        for s, p in self.state["positions"].items():
                            if p:
                                entry = p.get("entry", 0)
                                q = p.get("qty", 0)
                                current = self.state["current_prices"].get(s, entry)
                                pnl_by_symbol[s] = (current - entry) * q
                        update_pnl(self.state["total_pnl"], pnl_by_symbol)
                        update_circuit_breaker(
                            (abs(self.state["daily_pnl"]) / self.state.get("initial_balance", 10000.0)) * 100 if self.state["daily_pnl"] < 0 else 0,
                            (abs(self.state["pnl"]) / self.state.get("initial_balance", 10000.0)) * 100 if self.state["pnl"] < 0 else 0
                        )
                        update_system_metrics(psutil.cpu_percent(), psutil.virtual_memory().percent)

                with self._lock:
                    self.state["last_update"] = datetime.now().isoformat()
                time.sleep(60)
        except Exception as e:
            with self._lock:
                self.state["status"] = f"error: {e}"
            update_bot_status("error")
            self._notify_error(str(e))
        finally:
            set_binance_connections(False, False)
            update_bot_status("stopped")

    def _run_loop(self):
        if self.mock_mode:
            self._run_mock()
        else:
            self._run_live()

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.state["status"] = "stopped"

    def _update_state(self, **kwargs):
        with self._lock:
            self.state.update(kwargs)

    def _get_state_copy(self):
        with self._lock:
            return copy.deepcopy(self.state)

    def get_state(self):
        s = self._get_state_copy()
        first_sym = s["symbols"][0] if s["symbols"] else "BTCUSDT"
        s["current_price"] = s["current_prices"].get(first_sym, 0.0)
        s["position"] = s["positions"].get(first_sym)
        sig = s["signals"].get(first_sym, {})
        s["ma_signal"] = sig.get("ma", "HOLD")
        s["ml_signal"] = sig.get("ml", "HOLD")
        s["enhanced_signal"] = sig.get("enhanced", "HOLD")
        s["last_signal"] = sig.get("consensus", "HOLD")
        return s