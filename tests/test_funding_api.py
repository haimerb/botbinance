from backend.api import funding


def test_router_prefix_and_routes():
    assert funding.router.prefix == "/api/funding"
    paths = {r.path for r in funding.router.routes}
    assert paths == {
        "/api/funding/status",
        "/api/funding/opportunities",
        "/api/funding/start",
        "/api/funding/stop",
    }


def test_status_uses_runner_deep_copy(monkeypatch):
    class FakeRunner:
        def get_state(self):
            return {"status": "stopped", "position": None}

    monkeypatch.setattr(funding, "funding_runner", FakeRunner())
    assert funding.funding_status({}) == {"status": "stopped", "position": None}


def test_opportunities_returns_list(monkeypatch):
    class FakeRunner:
        def get_state(self):
            return {"opportunities": [{"symbol": "BTCUSDT"}]}

    monkeypatch.setattr(funding, "funding_runner", FakeRunner())
    assert funding.funding_opportunities({}) == {
        "opportunities": [{"symbol": "BTCUSDT"}]
    }
