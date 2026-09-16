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