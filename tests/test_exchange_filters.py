from src.execution.exchange_filters import ExchangeFilters, SymbolFilters


def _filters():
    ef = ExchangeFilters()
    ef._filters["BTCUSDT"] = SymbolFilters(
        symbol="BTCUSDT",
        step_size=0.00001,
        min_qty=0.00001,
        max_qty=9000.0,
        tick_size=0.01,
        min_notional=5.0,
    )
    return ef


class FakeClient:
    def exchange_info(self, symbol=None):
        return {
            "symbols": [{
                "symbol": symbol,
                "filters": [
                    {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "1000"},
                    {"filterType": "PRICE_FILTER", "tickSize": "0.01"},
                    {"filterType": "NOTIONAL", "minNotional": "5.0"},
                ],
            }]
        }


def test_round_quantity_down_to_step():
    ef = _filters()
    assert ef.round_quantity(0.00123456, 0.00001) == 0.00123
    assert ef.round_quantity(0.00199999, 0.00001) == 0.00199


def test_round_quantity_zero_step_is_noop():
    ef = _filters()
    assert ef.round_quantity(0.00123, 0.0) == 0.00123


def test_round_price_to_tick():
    ef = _filters()
    assert ef.round_price(65000.019, 0.01) == 65000.02


def test_normalize_rejects_below_min_notional():
    ef = ExchangeFilters()
    qty, price, error = ef.normalize_order(FakeClient(), "BTCUSDT", 0.00005, 65000.0)
    assert error is not None


def test_normalize_rejects_below_min_qty():
    ef = ExchangeFilters()
    qty, price, error = ef.normalize_order(FakeClient(), "BTCUSDT", 0.0001, 65000.0)
    assert error is not None


def test_normalize_accepts_valid_order():
    ef = ExchangeFilters()
    qty, price, error = ef.normalize_order(FakeClient(), "BTCUSDT", 0.00123456, 65000.019)
    assert error is None
    assert qty == 0.001
    assert price == 65000.02


def test_load_and_cache_filters():
    ef = ExchangeFilters()
    filt = ef.load(FakeClient(), "BTCUSDT")
    assert filt is not None
    assert filt.step_size == 0.001
    assert filt.min_notional == 5.0
    assert ef.get("BTCUSDT") is filt
