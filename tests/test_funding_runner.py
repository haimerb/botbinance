import pytest

from backend.services.funding_runner import FundingRunner
from src.execution.funding_executor import FundingPosition
from src.strategy.funding_gate import FundingDecision


class FakeOpp:
    def __init__(self, symbol="BTCUSDT", rate=0.0001, basis_pct=-0.02):
        self.symbol = symbol
        self.funding_rate = rate
        self.annual_pct = rate * 3 * 365 * 100
        self.annual_net_pct = self.annual_pct - 5
        self.basis_pct = basis_pct
        self.mark_price = 60000.0


class FakeScanner:
    def __init__(self, opportunities):
        self.opportunities = opportunities

    def scan(self, symbols):
        return self.opportunities


class FakeExecutor:
    def __init__(self, *, open_ok=True, close_ok=True):
        self.open_ok = open_ok
        self.close_ok = close_ok
        self.opened = []
        self.closed = []
        self.open_kwargs = []

    def open(self, symbol, quantity, rate, mark_price=0, **kwargs):
        from src.execution.funding_executor import FundingExecutionResult
        self.open_kwargs.append(kwargs)
        if not self.open_ok:
            return FundingExecutionResult(ok=False, error="perp rechazado")
        return FundingExecutionResult(
            ok=True,
            position=FundingPosition(symbol, quantity, mark_price, rate,
                                     spot_order_id=1, perp_order_id=2),
        )

    def close(self, position):
        from src.execution.funding_executor import FundingExecutionResult
        self.closed.append(position)
        return FundingExecutionResult(ok=bool(self.close_ok))


class FakeFutures:
    def __init__(self, rate=0.0001):
        self.rate = rate

    def mark_price(self, symbol):
        return {"lastFundingRate": str(self.rate)}


class FakeGate:
    def __init__(self, scores):
        self.scores = scores

    def evaluate(self, candidate, history):
        allowed, reason, score = self.scores.get(
            candidate.symbol, (True, "ok", candidate.net_annual_pct)
        )
        return FundingDecision(candidate.symbol, allowed, reason, score)


class FakeHistory:
    def __init__(self, rates=None):
        self.rates = rates or [0.0001] * 10

    def funding(self, symbol, limit=100):
        return [{"fundingRate": str(r)} for r in self.rates[:limit]]


def _runner(scanner, executor, futures, *, gate=None, history_client=None):
    r = FundingRunner(dry_run=True)
    r.inject(scanner=scanner, executor=executor, gate=gate,
             history_client=history_client)
    r._futures_client = futures
    r._symbols = ["BTCUSDT"]
    return r


def test_initial_state_is_stopped_and_no_position():
    runner = FundingRunner()
    state = runner.get_state()
    assert state["status"] == "stopped"
    assert state["position"] is None
    assert state["cycles"] == 0


def test_tick_opens_best_opportunity():
    scanner = FakeScanner([FakeOpp()])
    executor = FakeExecutor()
    runner = _runner(scanner, executor, FakeFutures())
    runner.tick()
    state = runner.get_state()
    assert state["position"]["symbol"] == "BTCUSDT"
    assert state["position"]["is_hedged"] is True
    assert state["cycles"] == 1
    assert len(executor.opened) == 0  # el fake no lo registra, pero la posición sí


def test_tick_records_opportunities_sorted():
    scanner = FakeScanner([FakeOpp("BTCUSDT", 0.0001), FakeOpp("ETHUSDT", 0.0003)])
    runner = _runner(scanner, FakeExecutor(), FakeFutures())
    runner.tick()
    assert len(runner.get_state()["opportunities"]) == 2


def test_tick_does_not_open_when_no_opportunities():
    runner = _runner(FakeScanner([]), FakeExecutor(), FakeFutures())
    runner.tick()
    assert runner.get_state()["position"] is None


def test_tick_does_not_reopen_when_position_exists():
    scanner = FakeScanner([FakeOpp()])
    executor = FakeExecutor()
    runner = _runner(scanner, executor, FakeFutures())
    runner.tick()
    runner.tick()
    assert len(executor.closed) == 0
    assert runner.get_state()["position"] is not None
    assert runner.get_state()["cycles"] == 2


def test_tick_closes_when_funding_turns_negative():
    scanner = FakeScanner([FakeOpp()])
    executor = FakeExecutor()
    futures = FakeFutures(rate=0.0001)
    runner = _runner(scanner, executor, futures)
    runner.tick()
    futures.rate = -0.0001
    runner.tick()
    assert runner.get_state()["position"] is None
    assert len(executor.closed) == 1


def test_tick_keeps_position_when_funding_still_positive():
    runner = _runner(FakeScanner([FakeOpp()]), FakeExecutor(), FakeFutures(rate=0.0001))
    runner.tick()
    runner.tick()
    assert runner.get_state()["position"] is not None


def test_executor_error_is_recorded_without_position():
    runner = _runner(FakeScanner([FakeOpp()]), FakeExecutor(open_ok=False), FakeFutures())
    runner.tick()
    state = runner.get_state()
    assert state["position"] is None
    assert "perp rechazado" in state["last_error"]


def test_get_state_returns_deep_copy():
    runner = _runner(FakeScanner([FakeOpp()]), FakeExecutor(), FakeFutures())
    runner.tick()
    snapshot = runner.get_state()
    snapshot["position"]["symbol"] = "MODIFICADO"
    assert runner.get_state()["position"]["symbol"] == "BTCUSDT"


def test_stop_sets_status_without_touching_position():
    runner = _runner(FakeScanner([FakeOpp()]), FakeExecutor(), FakeFutures())
    runner.tick()
    runner.stop()
    state = runner.get_state()
    assert state["status"] == "stopped"
    assert state["position"] is not None


def test_gate_rejects_all_opportunities():
    gate = FakeGate({"BTCUSDT": (False, "funding_extremo", -1)})
    runner = _runner(
        FakeScanner([FakeOpp()]), FakeExecutor(), FakeFutures(),
        gate=gate, history_client=FakeHistory(),
    )
    runner.tick()
    state = runner.get_state()
    assert state["position"] is None
    assert state["opportunities"][0]["gate_allowed"] is False
    assert state["opportunities"][0]["gate_reason"] == "funding_extremo"


def test_gate_ranks_by_score_instead_of_scanner_order():
    gate = FakeGate({
        "BTCUSDT": (True, "ok", 4.0),
        "ETHUSDT": (True, "ok", 15.0),
    })
    scanner = FakeScanner([FakeOpp("BTCUSDT"), FakeOpp("ETHUSDT", 0.0003)])
    runner = _runner(
        scanner, FakeExecutor(), FakeFutures(),
        gate=gate, history_client=FakeHistory(),
    )
    runner.tick()
    assert runner.get_state()["position"]["symbol"] == "ETHUSDT"


def test_runner_requests_maker_entry_from_executor():
    executor = FakeExecutor()
    runner = _runner(FakeScanner([FakeOpp()]), executor, FakeFutures())
    runner.tick()
    assert executor.open_kwargs[0]["maker"] is True
    assert "maker_timeout" in executor.open_kwargs[0]
    assert runner.get_state()["execution"]["maker"] is True


def test_accounting_separates_funding_basis_and_fees():
    futures = FakeFutures(rate=0.0001)
    runner = _runner(FakeScanner([FakeOpp(basis_pct=0.5)]), FakeExecutor(), futures)
    runner.tick()
    with runner._lock:
        runner.state["position"]["opened_at"] -= 8 * 3600
    futures.rate = -0.0001
    runner.tick()
    accounting = runner.get_state()["accounting"]
    assert accounting["funding"] > 0
    assert accounting["fees"] > 0
    assert accounting["basis"] < 0
    assert accounting["net"] < accounting["funding"]
