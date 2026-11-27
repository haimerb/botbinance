from src.data.binance_client import BinanceDataClient, KLINE_API_MAX_LIMIT


STEP_MS = 3_600_000  # 1h


def make_klines(first_open_ms, count):
    """Klines sintéticas (una por hora) empezando en first_open_ms."""
    rows = []
    open_ms = first_open_ms
    for _ in range(count):
        rows.append([
            str(open_ms), "100.0", "110.0", "90.0", "105.0", "10.0",
            str(open_ms + 3_599_999), "0", "0", "0", "0", "0",
        ])
        open_ms += STEP_MS
    return rows


class FakeSpot:
    """Imita a Spot.klines: sin endTime devuelve las más recientes; con
    endTime solo las velas con open time <= endTime."""

    def __init__(self, universe):
        self.universe = universe
        self.calls = []

    def klines(self, symbol, interval, limit=None, endTime=None, **kwargs):
        self.calls.append({"limit": limit, "endTime": endTime})
        rows = self.universe
        if endTime is not None:
            rows = [k for k in rows if int(k[0]) <= endTime]
        return rows[-limit:] if limit else rows


def _client_with(universe):
    client = BinanceDataClient(api_key="k", api_secret="s")
    client.client = FakeSpot(universe)
    return client


def test_limit_within_api_max_makes_one_call():
    universe = make_klines(0, 800)
    client = _client_with(universe)

    df = client.fetch_klines("BTCUSDT", "1h", limit=500)

    assert len(client.client.calls) == 1
    assert client.client.calls[0]["endTime"] is None
    assert len(df) == 500
    # las 500 más recientes, en orden ascendente
    assert df["timestamp"].is_monotonic_increasing
    assert int(df["timestamp"].iloc[0].value // 10**6) == (800 - 500) * STEP_MS


def test_paginates_beyond_api_max():
    universe = make_klines(0, 3500)
    client = _client_with(universe)

    df = client.fetch_klines("BTCUSDT", "1h", limit=3500)

    assert len(client.client.calls) == 4  # 1000 + 1000 + 1000 + 500
    assert client.client.calls[0]["endTime"] is None
    assert client.client.calls[1]["endTime"] is not None
    assert len(df) == 3500
    assert df["timestamp"].is_unique
    assert df["timestamp"].is_monotonic_increasing
    first_ms = int(df["timestamp"].iloc[0].value // 10**6)
    last_ms = int(df["timestamp"].iloc[-1].value // 10**6)
    assert (last_ms - first_ms) // STEP_MS == 3499


def test_stops_at_history_start_when_universe_is_short():
    universe = make_klines(0, 2500)
    client = _client_with(universe)

    df = client.fetch_klines("BTCUSDT", "1h", limit=3500)

    assert len(df) == 2500  # no hay más historial; no crash ni relleno
    assert df["timestamp"].is_unique


def test_numeric_columns_are_float():
    import pandas as pd

    universe = make_klines(0, 600)
    client = _client_with(universe)

    df = client.fetch_klines("BTCUSDT", "1h", limit=100)

    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
    for col in ["open", "high", "low", "close", "volume"]:
        assert pd.api.types.is_float_dtype(df[col])
