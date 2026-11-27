import copy
import threading
import time

from src.config import (
    FUNDING_ENABLED,
    FUNDING_EVENT_BLACKOUT_MINUTES,
    FUNDING_EXIT_IF_NEGATIVE,
    FUNDING_HISTORY_BASE_URL,
    FUNDING_HISTORY_WINDOW,
    FUNDING_LEVERAGE,
    FUNDING_MAKER_FEE,
    FUNDING_MAKER_PRICE_OFFSET,
    FUNDING_MAKER_TIMEOUT_SECONDS,
    FUNDING_MAX_BASIS_PCT,
    FUNDING_MAX_ZSCORE,
    FUNDING_MIN_ANNUAL_PCT,
    FUNDING_MIN_FALLBACK_ANNUAL_PCT,
    FUNDING_MIN_INTERVALS,
    FUNDING_MIN_PERSISTENCE_PROB,
    FUNDING_NOTIONAL_USDT,
    FUNDING_PERSISTENCE_MIN_SAMPLES,
    FUNDING_PERSISTENCE_TARGET_RATE,
    FUNDING_SYMBOLS,
    FUNDING_TAKER_FEE,
    FUNDING_USE_MAKER,
    FUNDING_USE_PERSISTENCE,
)
from src.data.binance_futures_client import BinanceFuturesClient
from src.data.funding_history import FundingHistoryClient
from src.execution.funding_executor import FundingExecutor
from src.execution.trade_executor import TradeExecutor
from src.strategy.event_calendar import EconomicCalendar
from src.strategy.funding_arbitrage import should_close
from src.strategy.funding_gate import (
    FundingCandidate,
    FundingDecision,
    FundingGate,
    rank_candidates,
)
from src.strategy.funding_persistence import FundingPersistenceModel
from src.strategy.funding_scanner import FundingScanner

FUNDING_INTERVAL_MS = 8 * 3_600_000


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
            "gate": {
                "enabled": False,
                "min_intervals": FUNDING_MIN_INTERVALS,
                "max_zscore": FUNDING_MAX_ZSCORE,
                "max_abs_basis_pct": FUNDING_MAX_BASIS_PCT,
                "blackout_minutes": FUNDING_EVENT_BLACKOUT_MINUTES,
                "persistence_enabled": FUNDING_USE_PERSISTENCE,
                "min_persistence_prob": FUNDING_MIN_PERSISTENCE_PROB,
                "persistence_trained": False,
            },
            "accounting": {
                "funding": 0.0,
                "basis": 0.0,
                "fees": 0.0,
                "net": 0.0,
            },
            "execution": {
                "maker": FUNDING_USE_MAKER,
                "maker_timeout": FUNDING_MAKER_TIMEOUT_SECONDS,
                "maker_offset": FUNDING_MAKER_PRICE_OFFSET,
            },
        }
        self._executor = None
        self._scanner = None
        self._futures_client = None
        self._spot_executor = None
        self._history_client = None
        self._gate = None
        self._persistence_trained = False

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
        self._history_client = FundingHistoryClient(
            BinanceFuturesClient(base_url=FUNDING_HISTORY_BASE_URL)
        )
        self._gate = FundingGate(
            min_intervals=FUNDING_MIN_INTERVALS,
            max_zscore=FUNDING_MAX_ZSCORE,
            max_abs_basis_pct=FUNDING_MAX_BASIS_PCT,
            history_window=FUNDING_HISTORY_WINDOW,
            calendar=EconomicCalendar(
                blackout_minutes=FUNDING_EVENT_BLACKOUT_MINUTES
            ),
            min_persistence_prob=(
                FUNDING_MIN_PERSISTENCE_PROB if FUNDING_USE_PERSISTENCE else 0.0
            ),
        )
        with self._lock:
            self.state["gate"]["enabled"] = True
        self._symbols = list(symbols or FUNDING_SYMBOLS)
        if FUNDING_LEVERAGE > 1:
            for symbol in self._symbols:
                try:
                    self._futures_client.set_leverage(symbol, FUNDING_LEVERAGE)
                except Exception:
                    pass

    def inject(self, *, scanner=None, executor=None, gate=None,
               history_client=None):
        """Inyección directa para tests."""
        if scanner is not None:
            self._scanner = scanner
        if executor is not None:
            self._executor = executor
        if gate is not None:
            self._gate = gate
            with self._lock:
                self.state["gate"]["enabled"] = True
        if history_client is not None:
            self._history_client = history_client
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
                opened = position.get("opened_at", time.time())
                intervals = max(
                    1,
                    round((time.time() - opened) * 1000 / FUNDING_INTERVAL_MS),
                )
                accounting = self.state["accounting"]
                accounting["funding"] += (
                    position.get("funding_rate", 0)
                    * FUNDING_NOTIONAL_USDT * intervals
                )
                accounting["fees"] += FUNDING_TAKER_FEE * FUNDING_NOTIONAL_USDT
                self._recalculate_net()
                self.state["position"] = None
            else:
                self.state["last_error"] = result.error

    def _maybe_open(self):
        self._ensure_persistence_model()
        opportunities = self._scanner.scan(self._symbols)
        if not opportunities:
            with self._lock:
                self.state["opportunities"] = []
                self.state["last_scan"] = time.time()
            return

        by_symbol = {o.symbol: o for o in opportunities}
        decisions = []
        enriched = []
        for opportunity in opportunities:
            history = self._funding_history(opportunity.symbol)
            candidate = FundingCandidate(
                symbol=opportunity.symbol,
                funding_rate=opportunity.funding_rate,
                net_annual_pct=opportunity.annual_net_pct,
                funding_time=int(time.time() * 1000),
                basis_pct=opportunity.basis_pct,
            )
            if self._gate is not None:
                decision = self._gate.evaluate(candidate, history)
            else:
                decision = FundingDecision(
                    opportunity.symbol,
                    candidate.funding_rate > 0,
                    "sin_gate",
                    candidate.net_annual_pct,
                )
            enriched.append({
                "symbol": opportunity.symbol,
                "funding_rate": opportunity.funding_rate,
                "annual_pct": opportunity.annual_pct,
                "annual_net_pct": opportunity.annual_net_pct,
                "basis_pct": opportunity.basis_pct,
                "gate_allowed": decision.allowed,
                "gate_reason": decision.reason,
                "score": round(decision.score, 4),
            })
            if decision.allowed:
                decisions.append(decision)

        with self._lock:
            self.state["opportunities"] = enriched
            self.state["last_scan"] = time.time()

        ranked = rank_candidates(decisions)
        if not ranked:
            return
        best = by_symbol[ranked[0].symbol]
        quantity = FUNDING_NOTIONAL_USDT / best.mark_price if best.mark_price else 0
        result = self._executor.open(
            best.symbol, quantity, best.funding_rate,
            mark_price=best.mark_price or 0,
            maker=FUNDING_USE_MAKER,
            maker_timeout=FUNDING_MAKER_TIMEOUT_SECONDS,
            maker_offset=FUNDING_MAKER_PRICE_OFFSET,
            min_fallback_annual_pct=FUNDING_MIN_FALLBACK_ANNUAL_PCT,
        )
        if result.ok and result.position is not None:
            basis_cost = max(best.basis_pct or 0, 0) / 100 * FUNDING_NOTIONAL_USDT
            entry_fee = (
                FUNDING_MAKER_FEE if FUNDING_USE_MAKER else FUNDING_TAKER_FEE
            ) * FUNDING_NOTIONAL_USDT
            with self._lock:
                accounting = self.state["accounting"]
                accounting["basis"] -= basis_cost
                accounting["fees"] += entry_fee
                self._recalculate_net()
                self.state["position"] = {
                    "symbol": result.position.symbol,
                    "quantity": result.position.quantity,
                    "entry_price": result.position.entry_price,
                    "funding_rate": result.position.funding_rate,
                    "is_hedged": result.position.is_hedged,
                    "opened_at": time.time(),
                    "basis_cost": basis_cost,
                    "entry_fee": entry_fee,
                }
        elif not result.ok:
            with self._lock:
                self.state["last_error"] = result.error

    def _ensure_persistence_model(self):
        if (self._gate is None or self._history_client is None
                or not FUNDING_USE_PERSISTENCE or self._persistence_trained):
            return
        history_by_symbol = {}
        limit = max(FUNDING_HISTORY_WINDOW * 10, 100)
        for symbol in self._symbols:
            try:
                rows = self._history_client.funding(symbol, limit=limit)
            except Exception:
                continue
            history_by_symbol[symbol] = self._rates_from_rows(rows)
        if not history_by_symbol:
            return
        model = FundingPersistenceModel(
            target_rate=FUNDING_PERSISTENCE_TARGET_RATE,
            min_samples=FUNDING_PERSISTENCE_MIN_SAMPLES,
        ).fit(history_by_symbol)
        self._gate.persistence_model = model
        self._persistence_trained = True
        with self._lock:
            self.state["gate"]["persistence_trained"] = True

    def _funding_history(self, symbol):
        if self._history_client is None:
            return []
        limit = max(FUNDING_HISTORY_WINDOW + FUNDING_MIN_INTERVALS, 30)
        try:
            rows = self._history_client.funding(symbol, limit=limit)
        except Exception:
            return []
        return self._rates_from_rows(rows)

    @staticmethod
    def _rates_from_rows(rows):
        return [
            float(row.get("funding_rate", row.get("fundingRate", 0)))
            for row in rows
        ]

    def _recalculate_net(self):
        accounting = self.state["accounting"]
        accounting["net"] = round(
            accounting["funding"] + accounting["basis"] - accounting["fees"], 4
        )

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
