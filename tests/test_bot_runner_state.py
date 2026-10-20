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
    monkeypatch.setattr(br_module, "add_trade", lambda *a, **k: 1)
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


def test_build_risk_manager_uses_user_config(runner):
    cfg = {
        "stop_loss_pct": 0.04,
        "take_profit_pct": 0.06,
        "trailing_stop_pct": 0.02,
        "trailing_activation_pct": 0.01,
        "time_exit_hours": 12,
        "partial_tp1_pct": 0.015,
        "partial_tp1_qty": 0.3,
        "partial_tp2_pct": 0.03,
        "partial_tp2_qty": 0.3,
        "partial_tp3_pct": 0.05,
        "partial_tp3_qty": 0.4,
        "enable_trailing": True,
        "enable_time_exit": True,
        "enable_partial_tp": True,
    }
    rm = runner._build_risk_manager("BTCUSDT", cfg)

    assert rm.stop_loss_pct == 0.04
    assert rm.take_profit_pct == 0.06
    assert rm.time_exit_hours == 12
    assert rm.partial_tp_levels == [(0.015, 0.3), (0.03, 0.3), (0.05, 0.4)]


def test_get_or_create_risk_manager_caches(runner):
    cfg = {"symbols": ["BTCUSDT"], "stop_loss_pct": 0.02}
    rm1 = runner._get_or_create_risk_manager("BTCUSDT", cfg)
    rm2 = runner._get_or_create_risk_manager("BTCUSDT", cfg)
    assert rm1 is rm2


def test_execute_partial_tp_keeps_remaining_position(runner):
    runner.set_user(1)
    runner.state["positions"]["BTCUSDT"] = {"side": "BUY", "entry": 100.0, "qty": 0.01}

    runner._execute_partial_tp("BTCUSDT", 101.0, 0.003)

    pos = runner.state["positions"]["BTCUSDT"]
    assert pos is not None
    assert pos["qty"] == pytest.approx(0.007)


def test_process_exits_full_close_uses_real_qty(runner):
    from src.risk.risk_manager import RiskManager, ExitReason
    runner.set_user(1)
    runner.state["positions"]["BTCUSDT"] = {"side": "BUY", "entry": 100.0, "qty": 0.01}
    rm = RiskManager(stop_loss_pct=0.02)
    rm.open_position(100.0, 0.01)

    runner._process_exits("BTCUSDT", 97.0, [(ExitReason.STOP_LOSS, "sl", None)], 0.01, rm)

    assert runner.state["positions"]["BTCUSDT"] is None
    assert rm.has_position() is False


def test_process_exits_partial_tp_keeps_position(runner):
    from src.risk.risk_manager import RiskManager, ExitReason
    runner.set_user(1)
    runner.state["positions"]["BTCUSDT"] = {"side": "BUY", "entry": 100.0, "qty": 0.01}
    rm = RiskManager(max_position_size=1.0)
    rm.open_position(100.0, 0.01)

    runner._process_exits("BTCUSDT", 101.0, [(ExitReason.PARTIAL_TP, "tp", 0.3)], 0.01, rm)

    pos = runner.state["positions"]["BTCUSDT"]
    assert pos is not None
    assert pos["qty"] == pytest.approx(0.007)


def test_initial_state_has_no_hardcoded_model_accuracy(runner):
    assert runner.state["model_accuracy"] is None
    assert runner.state["model_loaded"] is False


def test_refresh_model_metrics_reads_real_values(runner, monkeypatch):
    class FakeStrategy:
        def get_metrics(self):
            return {
                "model_loaded": True,
                "model_accuracy": 0.6123,
                "up_recall": 0.55,
                "up_precision": 0.60,
                "vol_accuracy": 0.70,
                "trained_at": "2026-01-01T00:00:00",
            }

    runner._ml_strategies["BTCUSDT"] = FakeStrategy()
    runner._refresh_model_metrics()

    assert runner.state["model_loaded"] is True
    assert runner.state["model_accuracy"] == 0.6123
    assert runner.state["model_up_recall"] == 0.55


def test_refresh_model_metrics_without_model(runner, monkeypatch):
    class NoModelStrategy:
        def get_metrics(self):
            return {"model_loaded": False, "model_accuracy": None}

    runner._ml_strategies["BTCUSDT"] = NoModelStrategy()
    runner._refresh_model_metrics()

    assert runner.state["model_loaded"] is False
    assert runner.state["model_accuracy"] is None
