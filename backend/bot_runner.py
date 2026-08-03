import threading
import time
import random
import math
import os
from datetime import datetime

from src.config import DEFAULT_SYMBOLS, INTERVAL, TRADE_QUANTITY, BALANCE_ALLOCATION_PCT
from src.data.binance_client import BinanceDataClient
from src.strategy.ma_crossover import MACrossoverStrategy
from src.strategy.ml_strategy import MLStrategy
from src.execution.trade_executor import TradeExecutor
from src.risk.risk_manager import RiskManager
from backend.database import add_trade, get_user_by_id
from backend.user_config import load_user_config


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
            "balance": 10000.0,
            "pnl": 0.0,
            "total_balance": 10000.0,
            "model_accuracy": 38.78,
            "last_update": None,
            "last_trade_id": 0,
        }
        self.mock_prices = {}
        self.mock_phases = {}
        self._risk_managers = {}

    def set_user(self, user_id: int):
        self.user_id = user_id
        if user_id:
            self.config = load_user_config(user_id)
            self.state["symbols"] = list(self.config.get("symbols", DEFAULT_SYMBOLS))
            alloc_pct = self.config.get("balance_allocation_pct", BALANCE_ALLOCATION_PCT)
            total_balance = 10000.0
            self.state["total_balance"] = total_balance
            self.state["balance"] = total_balance * (alloc_pct / 100.0)
            self.state["initial_balance"] = self.state["balance"]
            symbols = self.state["symbols"]
            for s in symbols:
                if s not in self.state["current_prices"]:
                    self.state["current_prices"][s] = 0.0
                    self.state["positions"][s] = None
                    self.state["signals"][s] = {"ma": "HOLD", "ml": "HOLD", "consensus": "HOLD"}
                    self.mock_prices[s] = 65000.0 if "BTC" in s else 3500.0 if "ETH" in s else 150.0
                    self.mock_phases[s] = random.random() * 6.28

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
        consensus = ma if ma == ml and ma != "HOLD" else "HOLD"
        return ma, ml, consensus

    def _mock_trade_logic(self, symbol: str, price: float, signal: str, qty: float):
        pos = self.state["positions"].get(symbol)
        if signal == "BUY" and not pos:
            cost = price * qty
            if self.state["balance"] < cost:
                return
            self.state["balance"] -= cost
            self.state["positions"][symbol] = {
                "side": "BUY", "entry": price, "qty": qty,
                "time": datetime.now().isoformat(),
            }
            if self.user_id:
                tid = add_trade(self.user_id, "BUY", price, qty, "entry", symbol=symbol)
                self.state["last_trade_id"] = tid
        elif signal == "SELL" and pos:
            entry = pos["entry"]
            pnl_pct = (price - entry) / entry * 100
            self.state["balance"] += price * qty
            self.state["pnl"] += (price - entry) * qty
            total_pos_value = sum(
                p.get("entry", 0) * p.get("qty", 0) for p in self.state["positions"].values() if p
            ) if any(self.state["positions"].values()) else 0
            self.state["total_balance"] = self.state["balance"] + total_pos_value
            self.state["positions"][symbol] = None
            if self.user_id:
                tid = add_trade(self.user_id, "SELL", price, qty, "exit", round(pnl_pct, 2), symbol=symbol)
                self.state["last_trade_id"] = tid

    def _run_mock(self):
        self.state["status"] = "running"
        while self.running:
            symbols = self.state["symbols"]
            if not symbols:
                time.sleep(2)
                continue
            with self._lock:
                for sym in symbols:
                    price = self._mock_tick(sym)
                    ma_sig, ml_sig, consensus = self._mock_signal()
                    self.state["current_prices"][sym] = price
                    self.state["signals"][sym] = {"ma": ma_sig, "ml": ml_sig, "consensus": consensus}
                    qty = self.config.get("trade_quantity", TRADE_QUANTITY)
                    self._mock_trade_logic(sym, price, consensus, qty)
                self.state["last_update"] = datetime.now().isoformat()
            time.sleep(2)

    def _run_live(self):
        try:
            user = get_user_by_id(self.user_id) if self.user_id else None
            if not user or not user.binance_api_key or not user.binance_api_secret:
                self.state["status"] = "error: API keys no configuradas"
                return

            os.environ["BINANCE_API_KEY"] = user.binance_api_key
            os.environ["BINANCE_API_SECRET"] = user.binance_api_secret

            cfg = self.config
            data_client = BinanceDataClient()
            ma_strategy = MACrossoverStrategy(
                fast_period=cfg.get("ma_fast_period", 9),
                slow_period=cfg.get("ma_slow_period", 21),
            )
            ml_strategy = MLStrategy(
                confidence_threshold=cfg.get("ml_confidence_threshold", 0.55),
            )
            executor = TradeExecutor()

            with self._lock:
                self.state["status"] = "running"
            while self.running:
                symbols = list(self.state["symbols"])
                if not symbols:
                    time.sleep(10)
                    continue

                for sym in symbols:
                    df = data_client.fetch_klines(sym, cfg.get("interval", "1h"))
                    if df.empty:
                        continue

                    ma_signal = ma_strategy.generate_signal(df)
                    ml_signal = ml_strategy.generate_signal(df)
                    consensus = ma_signal if ma_signal == ml_signal and ma_signal != "HOLD" else "HOLD"

                    price = executor.get_symbol_price(sym)
                    if price == 0.0:
                        continue

                    with self._lock:
                        self.state["current_prices"][sym] = price
                        self.state["signals"][sym] = {"ma": ma_signal, "ml": ml_signal, "consensus": consensus}

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
                        )
                        self._risk_managers[sym] = rm
                    elif cfg.get("ai_stop_loss_enabled", False):
                        atr = df["atr_ratio"].iloc[-1] if "atr_ratio" in df.columns else 0.02
                        sl = min(max(atr * 1.5, 0.01), 0.05)
                        tp = min(max(atr * 3, 0.02), 0.08)
                        rm.set_dynamic_levels(sl, tp)

                    qty = cfg.get("trade_quantity", TRADE_QUANTITY)

                    if rm.has_position():
                        if rm.check_stop_loss(price):
                            executor.execute_order("SELL", qty, sym)
                            rm.close_position()
                            with self._lock:
                                self.state["positions"][sym] = None
                            if self.user_id:
                                tid = add_trade(self.user_id, "SELL", price, qty, "stop_loss", symbol=sym)
                                with self._lock:
                                    self.state["last_trade_id"] = tid
                        elif rm.check_take_profit(price):
                            executor.execute_order("SELL", qty, sym)
                            rm.close_position()
                            with self._lock:
                                self.state["positions"][sym] = None
                            if self.user_id:
                                tid = add_trade(self.user_id, "SELL", price, qty, "take_profit", symbol=sym)
                                with self._lock:
                                    self.state["last_trade_id"] = tid
                    elif consensus == "BUY":
                        if rm.open_position(price, qty):
                            executor.execute_order("BUY", qty, sym)
                            with self._lock:
                                self.state["positions"][sym] = {
                                    "side": "BUY", "entry": price, "qty": qty,
                                    "time": datetime.now().isoformat(),
                                }
                            if self.user_id:
                                tid = add_trade(self.user_id, "BUY", price, qty, "entry", symbol=sym)
                                with self._lock:
                                    self.state["last_trade_id"] = tid
                    elif consensus == "SELL" and rm.has_position():
                        executor.execute_order("SELL", qty, sym)
                        rm.close_position()
                        with self._lock:
                            self.state["positions"][sym] = None
                        if self.user_id:
                            tid = add_trade(self.user_id, "SELL", price, qty, "exit", symbol=sym)
                            with self._lock:
                                self.state["last_trade_id"] = tid

                    with self._lock:
                        total_pos_value = sum(
                            p.get("entry", 0) * p.get("qty", 0) for p in self.state["positions"].values() if p
                        )
                        self.state["total_balance"] = self.state["balance"] + total_pos_value

                with self._lock:
                    self.state["last_update"] = datetime.now().isoformat()
                time.sleep(60)
        except Exception as e:
            with self._lock:
                self.state["status"] = f"error: {e}"

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
            return dict(self.state)

    def get_state(self):
        s = self._get_state_copy()
        first_sym = s["symbols"][0] if s["symbols"] else "BTCUSDT"
        s["current_price"] = s["current_prices"].get(first_sym, 0.0)
        s["position"] = s["positions"].get(first_sym)
        sig = s["signals"].get(first_sym, {})
        s["ma_signal"] = sig.get("ma", "HOLD")
        s["ml_signal"] = sig.get("ml", "HOLD")
        s["last_signal"] = sig.get("consensus", "HOLD")
        return s