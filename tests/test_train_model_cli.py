import sys

import train_model


def test_train_model_cli_parses_args(monkeypatch):
    captured = {}

    def fake_train_model(symbols=None, interval=None, limit=5000):
        captured["symbols"] = symbols
        captured["interval"] = interval
        captured["limit"] = limit

    monkeypatch.setattr(train_model, "train_model", fake_train_model)

    train_model.main(["--symbols", "ETHUSDT", "BNBUSDT", "--interval", "4h", "--limit", "1500"])

    assert captured["symbols"] == ["ETHUSDT", "BNBUSDT"]
    assert captured["interval"] == "4h"
    assert captured["limit"] == 1500


def test_train_model_cli_defaults(monkeypatch):
    from src.config import DEFAULT_SYMBOLS, INTERVAL
    captured = {}

    def fake_train_model(symbols=None, interval=None, limit=5000):
        captured["symbols"] = symbols
        captured["interval"] = interval
        captured["limit"] = limit

    monkeypatch.setattr(train_model, "train_model", fake_train_model)

    train_model.main([])

    assert captured["symbols"] == DEFAULT_SYMBOLS
    assert captured["interval"] == INTERVAL
    assert captured["limit"] == 5000
