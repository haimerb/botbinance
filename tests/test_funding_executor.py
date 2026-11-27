import pytest

from src.execution.funding_executor import FundingExecutor, FundingPosition
from src.execution.trade_executor import OrderResult


class FakeSpotExecutor:
    def __init__(self, *, fail_buy=False, fail_sell=False):
        self.fail_buy = fail_buy
        self.fail_sell = fail_sell
        self.calls = []

    def execute_order(self, side, quantity, symbol="BTCUSDT", order_type="MARKET"):
        self.calls.append((side, quantity, symbol))
        if side == "BUY" and self.fail_buy:
            return OrderResult.failure(side, symbol, quantity, "sin saldo")
        if side == "SELL" and self.fail_sell:
            return OrderResult.failure(side, symbol, quantity, "sell rechazado")
        return OrderResult(ok=True, side=side, symbol=symbol, quantity=quantity,
                           order_id=len(self.calls), status="FILLED",
                           filled_qty=quantity, avg_price=60000.0)


class FakeFuturesClient:
    def __init__(self, *, fail_order=False):
        self.fail_order = fail_order
        self.calls = []

    def set_margin_type(self, symbol, margin_type):
        self.calls.append(("margin", symbol, margin_type))
        return {}

    def set_leverage(self, symbol, leverage):
        self.calls.append(("leverage", symbol, leverage))
        return {}

    def place_order(self, symbol, side, quantity, **kwargs):
        self.calls.append((side, symbol, quantity, kwargs))
        if self.fail_order:
            raise RuntimeError("perp sin liquidez")
        return {"orderId": 99, "status": "FILLED"}


def test_open_creates_hedged_position():
    spot, futures = FakeSpotExecutor(), FakeFuturesClient()
    executor = FundingExecutor(spot, futures, dry_run=True)
    result = executor.open("BTCUSDT", 0.01, 0.0001, mark_price=61000)

    assert result.ok is True
    assert result.position.is_hedged is True
    assert spot.calls == [("BUY", 0.01, "BTCUSDT")]
    assert any(c[0] == "SELL" for c in futures.calls)


def test_open_uses_isolated_margin_and_leverage_one():
    spot, futures = FakeSpotExecutor(), FakeFuturesClient()
    FundingExecutor(spot, futures, dry_run=True).open("BTCUSDT", 0.01, 0.0001)
    assert ("margin", "BTCUSDT", "ISOLATED") in futures.calls
    assert ("leverage", "BTCUSDT", 1) in futures.calls


def test_open_rejects_non_positive_quantity():
    executor = FundingExecutor(FakeSpotExecutor(), FakeFuturesClient())
    result = executor.open("BTCUSDT", 0, 0.0001)
    assert result.ok is False
    assert "positiva" in result.error


def test_open_when_spot_fails_does_not_touch_futures():
    spot = FakeSpotExecutor(fail_buy=True)
    futures = FakeFuturesClient()
    result = FundingExecutor(spot, futures).open("BTCUSDT", 0.01, 0.0001)
    assert result.ok is False
    assert futures.calls == []
    assert "spot" in result.error


def test_open_when_perp_fails_closes_spot_immediately():
    spot = FakeSpotExecutor()
    futures = FakeFuturesClient(fail_order=True)
    result = FundingExecutor(spot, futures).open("BTCUSDT", 0.01, 0.0001)
    assert result.ok is False
    assert spot.calls == [("BUY", 0.01, "BTCUSDT"), ("SELL", 0.01, "BTCUSDT")]
    assert "spot cerrado" in result.error


def test_close_buys_perp_with_reduce_only_then_sells_spot():
    spot, futures = FakeSpotExecutor(), FakeFuturesClient()
    executor = FundingExecutor(spot, futures, dry_run=False)
    position = FundingPosition("BTCUSDT", 0.01, 60000, 0.0001,
                               spot_order_id=1, perp_order_id=2)
    result = executor.close(position)
    assert result.ok is True
    assert spot.calls == [("SELL", 0.01, "BTCUSDT")]
    perp_calls = [c for c in futures.calls if c[0] == "BUY"]
    assert len(perp_calls) == 1
    assert perp_calls[0][3].get("reduceOnly") is True


def test_close_in_dry_run_does_not_send_perp_order():
    spot, futures = FakeSpotExecutor(), FakeFuturesClient()
    executor = FundingExecutor(spot, futures, dry_run=True)
    position = FundingPosition("BTCUSDT", 0.01, 60000, 0.0001)
    executor.close(position)
    assert [c[0] for c in futures.calls] == []
    assert spot.calls == [("SELL", 0.01, "BTCUSDT")]
