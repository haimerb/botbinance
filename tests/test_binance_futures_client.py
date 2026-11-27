import pytest

from src.data.binance_futures_client import BinanceFuturesClient


class FakeUMFutures:
    def __init__(self, **kwargs):
        self.calls = []
        self.kwargs = kwargs

    def mark_price(self, symbol):
        self.calls.append(("mark_price", symbol))
        return {
            "symbol": symbol,
            "markPrice": "61757.4",
            "indexPrice": "61782.5",
            "lastFundingRate": "0.0001",
            "nextFundingTime": 1795766400000,
        }

    def funding_rate(self, **kwargs):
        self.calls.append(("funding_rate", kwargs))
        return [{"fundingRate": "0.0001", "fundingTime": 1795680000001}]

    def new_order(self, **kwargs):
        self.calls.append(("new_order", kwargs))
        return {"orderId": 1, "status": "FILLED"}

    def balance(self):
        return [{"asset": "USDT", "availableBalance": "1000"}]

    def position_risk(self):
        return []

    def change_leverage(self, **kwargs):
        self.calls.append(("change_leverage", kwargs))
        return {"leverage": kwargs["leverage"]}

    def change_margin_type(self, **kwargs):
        self.calls.append(("change_margin_type", kwargs))
        return {"code": 200}

    def exchange_info(self, **kwargs):
        return {"symbols": [{"symbol": "BTCUSDT"}]}


def _client(monkeypatch):
    fake = FakeUMFutures()

    def fake_umfutures(**kwargs):
        fake.kwargs = kwargs
        return fake

    monkeypatch.setattr("src.data.binance_futures_client.UMFutures", fake_umfutures)
    return BinanceFuturesClient(api_key="key", api_secret="secret"), fake


def test_client_uses_explicit_credentials_and_futures_url(monkeypatch):
    client, fake = _client(monkeypatch)
    assert fake.kwargs["key"] == "key"
    assert fake.kwargs["secret"] == "secret"
    assert "binancefuture" in fake.kwargs["base_url"] or "fapi" in fake.kwargs["base_url"]


def test_client_accepts_base_url_override(monkeypatch):
    fake = FakeUMFutures()

    def fake_umfutures(**kwargs):
        fake.kwargs = kwargs
        return fake

    monkeypatch.setattr("src.data.binance_futures_client.UMFutures", fake_umfutures)
    BinanceFuturesClient(api_key="k", api_secret="s",
                         base_url="https://fapi.binance.com")
    assert fake.kwargs["base_url"] == "https://fapi.binance.com"


def test_client_falls_back_to_global_credentials(monkeypatch):
    captured = {}

    def fake_umfutures(**kwargs):
        captured.update(kwargs)
        return FakeUMFutures()

    monkeypatch.setattr("src.data.binance_futures_client.UMFutures", fake_umfutures)
    BinanceFuturesClient()
    assert captured["key"] is not None
    assert captured["secret"] is not None


def test_mark_price_returns_funding_fields(monkeypatch):
    client, fake = _client(monkeypatch)
    result = client.mark_price("BTCUSDT")
    assert result["lastFundingRate"] == "0.0001"
    assert ("mark_price", "BTCUSDT") in fake.calls


def test_funding_rate_forwards_symbol_and_limit(monkeypatch):
    client, fake = _client(monkeypatch)
    client.funding_rate("ETHUSDT", limit=50)
    assert ("funding_rate", {"symbol": "ETHUSDT", "limit": 50}) in fake.calls


def test_place_short_order_uses_sell_side(monkeypatch):
    client, fake = _client(monkeypatch)
    result = client.place_order("BTCUSDT", "SELL", 0.01)
    assert result["status"] == "FILLED"
    order = [c for c in fake.calls if c[0] == "new_order"][0][1]
    assert order["side"] == "SELL"
    assert order["quantity"] == 0.01


def test_set_leverage_and_margin_type(monkeypatch):
    client, fake = _client(monkeypatch)
    client.set_leverage("BTCUSDT", 2)
    client.set_margin_type("BTCUSDT")
    assert any(c[0] == "change_leverage" for c in fake.calls)
    assert any(c[0] == "change_margin_type" for c in fake.calls)


def test_balance_and_positions_side_effects_free(monkeypatch):
    client, _ = _client(monkeypatch)
    assert client.balance()[0]["asset"] == "USDT"
    assert client.positions() == []
