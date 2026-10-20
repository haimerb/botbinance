import pytest

from src.risk.risk_manager import RiskManager


def test_open_position():
    rm = RiskManager(stop_loss_pct=0.02, take_profit_pct=0.03, max_position_size=0.01)
    assert rm.open_position(100.0, 0.005) is True
    assert rm.has_position() is True
    assert rm.position.entry_price == 100.0


def test_position_exceeds_max_size():
    rm = RiskManager(max_position_size=0.01)
    assert rm.open_position(100.0, 0.02) is False
    assert rm.has_position() is False


def test_stop_loss_triggered():
    rm = RiskManager(stop_loss_pct=0.02)
    rm.open_position(100.0, 0.005)
    assert rm.check_stop_loss(97.0) is True


def test_stop_loss_not_triggered():
    rm = RiskManager(stop_loss_pct=0.02)
    rm.open_position(100.0, 0.005)
    assert rm.check_stop_loss(99.0) is False


def test_take_profit_triggered():
    rm = RiskManager(take_profit_pct=0.03)
    rm.open_position(100.0, 0.005)
    assert rm.check_take_profit(104.0) is True


def test_take_profit_not_triggered():
    rm = RiskManager(take_profit_pct=0.03)
    rm.open_position(100.0, 0.005)
    assert rm.check_take_profit(102.0) is False


def test_close_position():
    rm = RiskManager()
    rm.open_position(100.0, 0.005)
    rm.close_position()
    assert rm.has_position() is False
    assert rm.position is None


def test_dynamic_levels():
    rm = RiskManager(stop_loss_pct=0.02, take_profit_pct=0.03)
    rm.set_dynamic_levels(0.03, 0.05)
    assert rm.stop_loss_pct == 0.03
    assert rm.take_profit_pct == 0.05


def test_has_position_no_position():
    rm = RiskManager()
    assert rm.has_position() is False


def test_partial_tp_returns_fraction_without_mutating_qty():
    rm = RiskManager(partial_tp_levels=[(0.01, 0.3), (0.02, 0.3)], enable_partial_tp=True)
    rm.open_position(100.0, 0.005)
    partials = rm.check_partial_take_profit(101.5)
    assert len(partials) == 1
    tp_price, frac, reason = partials[0]
    assert tp_price == pytest.approx(101.0)
    assert frac == 0.3
    assert reason.value == "partial_tp"
    assert rm.position.quantity == 0.005
    assert len(rm.position.take_profit_levels) == 1


def test_check_all_exits_includes_partial_fraction():
    rm = RiskManager(partial_tp_levels=[(0.01, 0.4)], enable_partial_tp=True)
    rm.open_position(100.0, 0.005)
    exits = rm.check_all_exits(101.5)
    partials = [e for e in exits if e[0].value == "partial_tp"]
    assert len(partials) == 1
    assert partials[0][2] == 0.4


def test_partial_tp_disabled_returns_empty():
    rm = RiskManager(partial_tp_levels=[(0.01, 0.3)], enable_partial_tp=False)
    rm.open_position(100.0, 0.005)
    assert rm.check_partial_take_profit(102.0) == []