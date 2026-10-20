import pytest

from src.execution.trade_executor import TradeExecutor, OrderResult


class FakeSpot:
    def __init__(self, order=None, error=None):
        self._order = order
        self._error = error

    def new_order(self, **kwargs):
        if self._error:
            raise self._error
        return self._order


def _executor_with(order=None, error=None):
    ex = TradeExecutor(api_key="k", api_secret="s")
    ex.client = FakeSpot(order=order, error=error)
    return ex


def test_order_success_returns_fill_details():
    order = {
        "orderId": 123,
        "status": "FILLED",
        "executedQty": "0.002",
        "cummulativeQuoteQty": "130000.0",
        "fills": [{"price": "65000.0", "qty": "0.002"}],
    }
    ex = _executor_with(order=order)
    result = ex.execute_order("BUY", 0.002, "BTCUSDT")

    assert isinstance(result, OrderResult)
    assert result.ok is True
    assert result.order_id == 123
    assert result.status == "FILLED"
    assert result.filled_qty == pytest.approx(0.002)
    assert result.avg_price == pytest.approx(65000.0)
    assert result.error is None


def test_order_failure_returns_not_ok():
    ex = _executor_with(error=RuntimeError("insufficient balance"))
    result = ex.execute_order("BUY", 0.002, "BTCUSDT")

    assert result.ok is False
    assert result.filled_qty == 0.0
    assert result.order_id is None
    assert "insufficient balance" in result.error


def test_avg_price_from_cummulative_quote_qty():
    order = {
        "orderId": 7,
        "status": "FILLED",
        "executedQty": "0.004",
        "cummulativeQuoteQty": "260.0",
        "fills": [],
    }
    ex = _executor_with(order=order)
    result = ex.execute_order("SELL", 0.004, "BTCUSDT")

    assert result.ok is True
    assert result.avg_price == pytest.approx(65000.0)


def test_order_failure_classmethod_defaults():
    result = OrderResult.failure("SELL", "ETHUSDT", 0.5, "boom")
    assert result.ok is False
    assert result.side == "SELL"
    assert result.symbol == "ETHUSDT"
    assert result.quantity == 0.5
    assert result.error == "boom"


class DryRunSpot:
    def __init__(self):
        self.new_order_called = False

    def ticker_price(self, symbol):
        return {"price": "65000.0"}

    def exchange_info(self, symbol=None):
        return {"symbols": [{"symbol": symbol, "filters": [
            {"filterType": "LOT_SIZE", "stepSize": "0.00001", "minQty": "0.00001", "maxQty": "9000"},
            {"filterType": "NOTIONAL", "minNotional": "5.0"},
        ]}]}

    def new_order(self, **kwargs):
        self.new_order_called = True
        raise AssertionError("dry-run no debe enviar órdenes reales")


def test_dry_run_does_not_send_order():
    ex = TradeExecutor(api_key="k", api_secret="s", dry_run=True)
    fake = DryRunSpot()
    ex.client = fake
    result = ex.execute_order("BUY", 0.001, "BTCUSDT")

    assert fake.new_order_called is False
    assert result.ok is True
    assert result.status == "DRY_RUN"
    assert result.filled_qty == pytest.approx(0.001)
    assert result.avg_price == pytest.approx(65000.0)

