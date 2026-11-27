from src.strategy.funding_scanner import FundingScanner


class FakeFuturesClient:
    def __init__(self, rates):
        self.rates = rates
        self.failed = set()

    def mark_price(self, symbol):
        if symbol in self.failed:
            raise RuntimeError("symbol no disponible")
        return {"lastFundingRate": str(self.rates[symbol])}


def test_scan_ranks_by_net_annual_return():
    client = FakeFuturesClient({"BTCUSDT": 0.0001, "ETHUSDT": 0.0003, "SOLUSDT": 0.00005})
    scanner = FundingScanner(client, min_annual_pct=0)
    opps = scanner.scan(list(client.rates))
    assert [o.symbol for o in opps] == ["ETHUSDT", "BTCUSDT", "SOLUSDT"]


def test_best_returns_top_opportunity():
    client = FakeFuturesClient({"BTCUSDT": 0.0001, "ETHUSDT": 0.0003})
    scanner = FundingScanner(client, min_annual_pct=0)
    assert scanner.best(list(client.rates)).symbol == "ETHUSDT"


def test_scan_filters_negative_and_below_threshold():
    client = FakeFuturesClient({"BTCUSDT": 0.0001, "ETHUSDT": -0.0002, "SOLUSDT": 0.000001})
    scanner = FundingScanner(client, min_annual_pct=8.0)
    assert [o.symbol for o in scanner.scan(list(client.rates))] == ["BTCUSDT"]


def test_scan_skips_symbols_that_raise():
    client = FakeFuturesClient({"BTCUSDT": 0.0001, "ETHUSDT": 0.0003})
    client.failed.add("ETHUSDT")
    scanner = FundingScanner(client, min_annual_pct=0)
    assert [o.symbol for o in scanner.scan(list(client.rates))] == ["BTCUSDT"]


def test_scan_empty_when_no_opportunities():
    client = FakeFuturesClient({"BTCUSDT": -0.0001})
    scanner = FundingScanner(client)
    assert scanner.scan(["BTCUSDT"]) == []
    assert scanner.best(["BTCUSDT"]) is None
