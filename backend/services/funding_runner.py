import copy
import threading
import time

from src.config import (
    FUNDING_ENABLED,
    FUNDING_EXIT_IF_NEGATIVE,
    FUNDING_LEVERAGE,
    FUNDING_MIN_ANNUAL_PCT,
    FUNDING_NOTIONAL_USDT,
    FUNDING_SYMBOLS,
)
from src.data.binance_futures_client import BinanceFuturesClient
from src.execution.funding_executor import FundingExecutor
from src.execution.trade_executor import TradeExecutor
from src.strategy.funding_arbitrage import should_close
from src.strategy.funding_scanner import FundingScanner


class FundingRunner:
    """Orquestador del arbitraje de funding, aislado del bot spot.

    Expone un ``tick()`` síncrono (testeable sin hilos) y un ``start()/stop()``
    que lo ejecuta periódicamente en un thread daemon.
    """

    def __init__(self, *, dry_run: bool = False, poll_interval: float = 300.0):
        self._lock = threading.Lock()
        self._thread = None
        self.running = False
        self.dry_run = dry_run
        self.poll_interval = poll_interval
        self.state = {
            "status": "stopped",
            "enabled": FUNDING_ENABLED,
            "dry_run": dry_run,
            "position": None,
            "opportunities": [],
            "last_scan": None,
            "last_error": None,
            "cycles": 0,
        }
        self._executor = None
        self._scanner = None
        self._futures_client = None
        self._spot_executor = None

    def configure(self, *, api_key=None, api_secret=None, symbols=None):
        """Construye dependencias con credenciales del usuario."""
        self._futures_client = BinanceFuturesClient(api_key, api_secret)
        self._spot_executor = TradeExecutor(
            api_key=api_key, api_secret=api_secret, dry_run=self.dry_run
        )
        self._executor = FundingExecutor(
            self._spot_executor, self._futures_client, dry_run=self.dry_run
        )
        self._scanner = FundingScanner(
            self._futures_client,
            min_annual_pct=FUNDING_MIN_ANNUAL_PCT,
            hold_days=30.0,
        )
        self._symbols = list(symbols or FUNDING_SYMBOLS)
        if FUNDING_LEVERAGE > 1:
            for symbol in self._symbols:
                try:
                    self._futures_client.set_leverage(symbol, FUNDING_LEVERAGE)
                except Exception:
                    pass

    def inject(self, *, scanner=None, executor=None):
        """Inyección directa para tests."""
        if scanner is not None:
            self._scanner = scanner
        if executor is not None:
            self._executor = executor
        self._symbols = list(FUNDING_SYMBOLS)

    def tick(self):
        """Un ciclo: evalúa la posición abierta o busca la mejor oportunidad."""
        with self._lock:
            self.state["cycles"] += 1
            self.state["last_error"] = None
        try:
            if self.state["position"] is not None:
                self._maybe_close(self.state["position"])
            else:
                self._maybe_open()
        except Exception as exc:
            with self._lock:
                self.state["last_error"] = str(exc)

    def _maybe_close(self, position):
        rate = self._current_rate(position["symbol"])
        if not should_close(rate, FUNDING_EXIT_IF_NEGATIVE):
            return
        result = self._executor.close(self._position_obj(position))
        with self._lock:
            if result.ok:
                self.state["position"] = None
            else:
                self.state["last_error"] = result.error

    def _maybe_open(self):
        opportunities = self._scanner.scan(self._symbols)
        with self._lock:
            self.state["opportunities"] = [
                {
                    "symbol": o.symbol,
                    "funding_rate": o.funding_rate,
                    "annual_pct": o.annual_pct,
                    "annual_net_pct": o.annual_net_pct,
                    "basis_pct": o.basis_pct,
                }
                for o in opportunities
            ]
            self.state["last_scan"] = time.time()
        if not opportunities:
            return
        best = opportunities[0]
        quantity = FUNDING_NOTIONAL_USDT / best.mark_price if best.mark_price else 0
        result = self._executor.open(
            best.symbol, quantity, best.funding_rate,
            mark_price=best.mark_price or 0,
        )
        if result.ok and result.position is not None:
            with self._lock:
                self.state["position"] = {
                    "symbol": result.position.symbol,
                    "quantity": result.position.quantity,
                    "entry_price": result.position.entry_price,
                    "funding_rate": result.position.funding_rate,
                    "is_hedged": result.position.is_hedged,
                    "opened_at": time.time(),
                }
        elif not result.ok:
            with self._lock:
                self.state["last_error"] = result.error

    def _current_rate(self, symbol):
        data = self._futures_client.mark_price(symbol)
        return float(data.get("lastFundingRate", 0) or 0)

    @staticmethod
    def _position_obj(data):
        from src.execution.funding_executor import FundingPosition
        return FundingPosition(
            symbol=data["symbol"],
            quantity=data["quantity"],
            entry_price=data["entry_price"],
            funding_rate=data["funding_rate"],
        )

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        with self._lock:
            self.state["status"] = "stopped"

    def _run_loop(self):
        with self._lock:
            self.state["status"] = "running"
        while self.running:
            self.tick()
            time.sleep(self.poll_interval)

    def get_state(self) -> dict:
        with self._lock:
            return copy.deepcopy(self.state)
