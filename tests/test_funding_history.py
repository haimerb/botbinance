from src.data.funding_history import FundingHistoryClient


class FakeFutures:
    def __init__(self, pages=None, mark_pages=None, index_pages=None, oi_pages=None):
        self.pages = pages or []
        self.mark_pages = mark_pages or []
        self.index_pages = index_pages or []
        self.oi_pages = oi_pages or []
        self.funding_calls = []
        self.kline_calls = []
        self.oi_calls = []

    def funding_rate(self, symbol, **kwargs):
        self.funding_calls.append(kwargs)
        rows = [r for page in self.pages for r in page]
        return self._filter(rows, "fundingTime", kwargs)

    def mark_price_klines(self, symbol, interval, **kwargs):
        self.kline_calls.append((interval, kwargs))
        rows = [r for page in self.mark_pages for r in page]
        return self._filter(rows, 0, kwargs, key_index=0)

    def index_price_klines(self, pair, interval, **kwargs):
        self.kline_calls.append((interval, kwargs))
        rows = [r for page in self.index_pages for r in page]
        return self._filter(rows, 0, kwargs, key_index=0)

    def open_interest_hist(self, symbol, period, **kwargs):
        self.oi_calls.append((period, kwargs))
        rows = [r for page in self.oi_pages for r in page]
        return self._filter(rows, "timestamp", kwargs)

    @staticmethod
    def _filter(rows, key, kwargs, key_index=None):
        start = kwargs.get("startTime")
        end = kwargs.get("endTime")
        limit = kwargs.get("limit", 1000)

        def ts(row):
            return int(row[key] if key_index is None else row[key_index])

        if start is not None:
            rows = [r for r in rows if ts(r) >= start]
        if end is not None:
            rows = [r for r in rows if ts(r) <= end]
        rows.sort(key=ts)
        return rows[:limit]


def _kline(t, price):
    return [t, str(price), str(price), str(price), str(price), "0", t + 1,
            "0", "0", "0", "0", "0"]


def test_funding_paginates_without_duplicates():
    t0, t1, t2 = 1000, 2000, 3000
    fake = FakeFutures(pages=[
        [
            {"fundingTime": t0, "fundingRate": "0.0001"},
            {"fundingTime": t1, "fundingRate": "0.0002"},
            {"fundingTime": t2, "fundingRate": "0.0003"},
        ],
    ])
    client = FundingHistoryClient(fake, funding_limit=2)
    rows = client.funding("BTCUSDT")
    assert [r["funding_time"] for r in rows] == [t0, t1, t2]
    assert len(fake.funding_calls) >= 2
    assert fake.funding_calls[1]["startTime"] == t1 + 1


def test_funding_respects_explicit_limit():
    fake = FakeFutures(
        pages=[[{"fundingTime": t, "fundingRate": "0.0001"} for t in range(1000, 5000, 1000)]]
    )
    rows = FundingHistoryClient(fake).funding("BTCUSDT", limit=2)
    assert len(rows) == 2
    assert fake.funding_calls[0]["limit"] == 2


def test_funding_stops_when_page_is_short():
    fake = FakeFutures(pages=[
        [{"fundingTime": 1000, "fundingRate": "0.0001"}]
    ])
    rows = FundingHistoryClient(fake, funding_limit=1000).funding("BTCUSDT")
    assert len(rows) == 1
    assert len(fake.funding_calls) == 1


def test_basis_uses_index_price_klines():
    t = 1000
    fake = FakeFutures(
        mark_pages=[[_kline(t, 101)]],
        index_pages=[[_kline(t, 100)]],
    )
    rows = FundingHistoryClient(fake).mark_index("BTCUSDT")
    assert abs(rows[0]["basis_pct"] - 1.0) < 1e-9
    assert rows[0]["mark_price"] == 101.0
    assert rows[0]["index_price"] == 100.0


def test_open_interest_maps_timestamp_and_value():
    fake = FakeFutures(oi_pages=[
        [{"timestamp": 1000, "openInterest": "12.5", "sumOpenInterestValue": "125000"}]
    ])
    rows = FundingHistoryClient(fake).open_interest("BTCUSDT")
    assert rows[0]["open_interest"] == 12.5
    assert rows[0]["open_interest_value"] == 125000.0


def test_open_interest_accepts_real_api_key_name():
    fake = FakeFutures(oi_pages=[
        [{"timestamp": 1000, "sumOpenInterest": "12.5",
          "sumOpenInterestValue": "125000"}]
    ])
    rows = FundingHistoryClient(fake).open_interest("BTCUSDT")
    assert rows[0]["open_interest"] == 12.5


def test_dataset_merges_funding_basis_and_open_interest():
    t = 1000
    fake = FakeFutures(
        pages=[[{"fundingTime": t, "fundingRate": "0.0001"}]],
        mark_pages=[[_kline(t, 101)]],
        index_pages=[[_kline(t, 100)]],
        oi_pages=[[{"timestamp": t, "openInterest": "12.5",
                    "sumOpenInterestValue": "125000"}]],
    )
    rows = FundingHistoryClient(fake).dataset("BTCUSDT", start_ms=t, end_ms=t + 1)
    assert len(rows) == 1
    assert rows[0]["funding_rate"] == 0.0001
    assert abs(rows[0]["basis_pct"] - 1.0) < 1e-9
    assert rows[0]["open_interest"] == 12.5
