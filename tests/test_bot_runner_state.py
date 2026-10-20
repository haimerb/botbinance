import pytest

import backend.services.bot_runner as br_module
from backend.services.bot_runner import BotRunner


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.setattr(br_module, "load_user_config", lambda uid: {
        "symbols": ["BTCUSDT"],
        "balance_allocation_pct": 100,
        "portfolio_allocation_mode": "equal",
        "max_daily_loss_pct": 5.0,
        "max_total_loss_pct": 10.0,
    })
    monkeypatch.setattr(br_module, "update_bot_status", lambda *a, **k: None)
    return BotRunner(mock_mode=True)


def test_set_user_first_time_sets_balance(runner):
    runner.set_user(1)
    assert runner.user_id == 1
    assert runner.state["balance"] == 10000.0
    assert runner.state["symbols"] == ["BTCUSDT"]


def test_ensure_user_same_user_does_not_reset_state(runner):
    runner.set_user(1)
    runner.state["balance"] = 1234.0
    runner.state["positions"]["BTCUSDT"] = {"side": "BUY", "entry": 60000, "qty": 0.01}
    runner.running = True

    runner.ensure_user(1)

    assert runner.state["balance"] == 1234.0
    assert runner.state["positions"]["BTCUSDT"] is not None


def test_set_user_same_user_while_running_preserves_positions(runner):
    runner.set_user(1)
    runner.running = True
    runner.state["balance"] = 500.0
    runner.state["positions"]["BTCUSDT"] = {"side": "BUY", "entry": 60000, "qty": 0.01}

    runner.set_user(1)

    assert runner.state["balance"] == 500.0
    assert runner.state["positions"]["BTCUSDT"] is not None


def test_set_user_different_user_resets_state(runner):
    runner.set_user(1)
    runner.running = True
    runner.state["balance"] = 500.0

    runner.set_user(2)

    assert runner.user_id == 2
    assert runner.state["balance"] == 10000.0


def test_set_user_stopped_same_user_resets_state(runner):
    runner.set_user(1)
    runner.running = False
    runner.state["balance"] = 777.0

    runner.set_user(1)

    assert runner.state["balance"] == 10000.0


def test_prepare_for_start_resets_state(runner):
    runner.set_user(1)
    runner.state["balance"] = 42.0

    runner.prepare_for_start()

    assert runner.state["balance"] == 10000.0
    assert runner._portfolio_manager is not None
