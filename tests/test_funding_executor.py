import pytest

from src.execution.funding_executor import FundingExecutor, FundingPosition
from src.execution.trade_executor import OrderResult


class FakeSpotExecutor:
    def __init__(self, *, fail_buy=False, fail_sell=False, statuses=None):
        self.fail_buy = fail_buy
        self.fail_sell = fail_sell
        self.calls = []
        self.details = []
        self.statuses = statuses or {}

    def execute_order(self, side, quantity, symbol="BTCUSDT",
                      order_type="MARKET", price=None, time_in_force=None):
        self.calls.append((side, quantity, symbol))
        self.details.append({
            "order_type": order_type, "price": price,
            "time_in_force": time_in_force,
        })
        if side == "BUY" and self.fail_buy:
            return OrderResult.failure(side, symbol, quantity, "sin saldo")
        if side == "SELL" and self.fail_sell:
            return OrderResult.failure(side, symbol, quantity, "sell rechazado")
        order_id = len(self.calls)
        return OrderResult(
            ok=True, side=side, symbol=symbol, quantity=quantity,
            order_id=order_id, status=self.statuses.get(order_id, "FILLED"),
            filled_qty=quantity, avg_price=price or 60000.0,
        )

    def get_symbol_price(self, symbol="BTCUSDT"):
        return 60000.0

    def query_order(self, symbol, order_id):
        return {"status": self.statuses.get(order_id, "FILLED")}

    def cancel_order(self, symbol, order_id):
        self.calls.append(("CANCEL", order_id, symbol))
        return {"status": "CANCELED"}


class SimulatedSpotExecutor(FakeSpotExecutor):
    def execute_order(self, side, quantity, symbol="BTCUSDT",
                      order_type="MARKET", price=None, time_in_force=None):
        result = super().execute_order(
            side, quantity, symbol, order_type, price, time_in_force
        )
        result.order_id = None
        return result


class FakeFuturesClient:
    def __init__(self, *, fail_order=False, maker_status="FILLED"):
        self.fail_order = fail_order
        self.maker_status = maker_status
        self.calls = []
        self.maker_calls = []

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

    def place_limit_order(self, symbol, side, quantity, price, **kwargs):
        self.maker_calls.append((side, symbol, quantity, price, kwargs))
        return {"orderId": 100, "status": self.maker_status}

    def query_order(self, symbol, order_id):
        return {"status": self.maker_status if order_id == 100 else "FILLED"}

    def cancel_order(self, symbol, order_id):
        self.calls.append(("CANCEL", order_id, symbol))
        return {"status": "CANCELED"}


def test_open_creates_hedged_position():
    spot, futures = FakeSpotExecutor(), FakeFuturesClient()
    executor = FundingExecutor(spot, futures, dry_run=True)
    result = executor.open("BTCUSDT", 0.01, 0.0001, mark_price=61000)

    assert result.ok is True
    assert result.position.is_hedged is True
    assert spot.calls == [("BUY", 0.01, "BTCUSDT")]
    assert futures.calls == []


def test_open_dry_run_marks_both_legs_as_hedged_without_real_ids():
    spot, futures = SimulatedSpotExecutor(), FakeFuturesClient()
    result = FundingExecutor(spot, futures, dry_run=True).open(
        "BTCUSDT", 0.01, 0.0001, mark_price=61000
    )
    assert result.ok is True
    assert result.position.spot_order_id == -1
    assert result.position.perp_order_id == -1
    assert result.position.is_hedged is True


def test_open_uses_isolated_margin_and_leverage_one():
    spot, futures = FakeSpotExecutor(), FakeFuturesClient()
    FundingExecutor(spot, futures, dry_run=False).open("BTCUSDT", 0.01, 0.0001)
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


def test_maker_uses_post_only_on_both_legs():
    spot, futures = FakeSpotExecutor(), FakeFuturesClient()
    result = FundingExecutor(spot, futures, dry_run=False).open(
        "BTCUSDT", 0.01, 0.0003, mark_price=60000, maker=True
    )
    assert result.ok
    assert spot.details[0]["order_type"] == "LIMIT"
    assert spot.details[0]["time_in_force"] == "GTX"
    assert spot.details[0]["price"] < 60000
    assert futures.maker_calls[0][3] > 60000
    assert futures.maker_calls[0][4]["post_only"] is True


def test_maker_timeout_falls_back_to_taker_with_high_edge():
    spot = FakeSpotExecutor(statuses={1: "NEW"})
    futures = FakeFuturesClient(maker_status="NEW")
    result = FundingExecutor(spot, futures, dry_run=False).open(
        "BTCUSDT", 0.01, 0.0003, mark_price=60000,
        maker=True, maker_timeout=0,
    )
    assert result.ok
    assert any(c[0] == "SELL" for c in futures.calls)
    assert result.position.is_hedged


def test_maker_timeout_without_edge_does_not_fallback():
    spot = FakeSpotExecutor(statuses={1: "NEW"})
    futures = FakeFuturesClient(maker_status="NEW")
    result = FundingExecutor(spot, futures, dry_run=False).open(
        "BTCUSDT", 0.01, 0.000001, mark_price=60000,
        maker=True, maker_timeout=0,
    )
    assert not result.ok
    assert "edge insuficiente" in result.error
    assert not any(c[0] == "SELL" for c in futures.calls)
