import json
from src.config import (
    DEFAULT_SYMBOLS, INTERVAL, TRADE_QUANTITY, STOP_LOSS_PCT,
    TAKE_PROFIT_PCT, MAX_POSITION_SIZE, MA_FAST_PERIOD, MA_SLOW_PERIOD,
    ML_CONFIDENCE_THRESHOLD, BALANCE_ALLOCATION_PCT,
)
from backend.database import get_or_create_user_config, update_user_config


DEFAULTS = {
    "symbols": DEFAULT_SYMBOLS,
    "interval": INTERVAL,
    "trade_quantity": TRADE_QUANTITY,
    "stop_loss_pct": STOP_LOSS_PCT,
    "take_profit_pct": TAKE_PROFIT_PCT,
    "max_position_size": MAX_POSITION_SIZE,
    "ma_fast_period": MA_FAST_PERIOD,
    "ma_slow_period": MA_SLOW_PERIOD,
    "ml_confidence_threshold": ML_CONFIDENCE_THRESHOLD,
    "balance_allocation_pct": BALANCE_ALLOCATION_PCT,
    "ai_stop_loss_enabled": False,
    "ai_optimize_enabled": False,
    "trailing_stop_pct": 0.01,
    "trailing_activation_pct": 0.015,
    "time_exit_hours": 24,
    "partial_tp1_pct": 0.015,
    "partial_tp1_qty": 0.3,
    "partial_tp2_pct": 0.03,
    "partial_tp2_qty": 0.3,
    "partial_tp3_pct": 0.05,
    "partial_tp3_qty": 0.4,
    "enable_trailing": True,
    "enable_time_exit": True,
    "enable_partial_tp": True,
    "max_daily_loss_pct": 5.0,
    "max_total_loss_pct": 10.0,
}


def load_user_config(user_id: int) -> dict:
    cfg = get_or_create_user_config(user_id)
    config = dict(DEFAULTS)
    config["symbols"] = json.loads(cfg.symbols) if cfg.symbols else list(DEFAULT_SYMBOLS)
    config["interval"] = cfg.interval if cfg.interval is not None else INTERVAL
    config["trade_quantity"] = cfg.trade_quantity if cfg.trade_quantity is not None else TRADE_QUANTITY
    config["stop_loss_pct"] = cfg.stop_loss_pct if cfg.stop_loss_pct is not None else 0.02
    config["take_profit_pct"] = cfg.take_profit_pct if cfg.take_profit_pct is not None else 0.03
    config["max_position_size"] = cfg.max_position_size if cfg.max_position_size is not None else 0.01
    config["ma_fast_period"] = cfg.ma_fast_period if cfg.ma_fast_period is not None else 9
    config["ma_slow_period"] = cfg.ma_slow_period if cfg.ma_slow_period is not None else 21
    config["ml_confidence_threshold"] = cfg.ml_confidence_threshold if cfg.ml_confidence_threshold is not None else 0.55
    config["balance_allocation_pct"] = cfg.balance_allocation_pct if cfg.balance_allocation_pct is not None else 100.0
    config["ai_stop_loss_enabled"] = bool(cfg.ai_stop_loss_enabled) if cfg.ai_stop_loss_enabled is not None else False
    config["ai_optimize_enabled"] = bool(cfg.ai_optimize_enabled) if cfg.ai_optimize_enabled is not None else False
    config["trailing_stop_pct"] = cfg.trailing_stop_pct if cfg.trailing_stop_pct is not None else 0.01
    config["trailing_activation_pct"] = cfg.trailing_activation_pct if cfg.trailing_activation_pct is not None else 0.015
    config["time_exit_hours"] = cfg.time_exit_hours if cfg.time_exit_hours is not None else 24
    config["partial_tp1_pct"] = cfg.partial_tp1_pct if cfg.partial_tp1_pct is not None else 0.015
    config["partial_tp1_qty"] = cfg.partial_tp1_qty if cfg.partial_tp1_qty is not None else 0.3
    config["partial_tp2_pct"] = cfg.partial_tp2_pct if cfg.partial_tp2_pct is not None else 0.03
    config["partial_tp2_qty"] = cfg.partial_tp2_qty if cfg.partial_tp2_qty is not None else 0.3
    config["partial_tp3_pct"] = cfg.partial_tp3_pct if cfg.partial_tp3_pct is not None else 0.05
    config["partial_tp3_qty"] = cfg.partial_tp3_qty if cfg.partial_tp3_qty is not None else 0.4
    config["enable_trailing"] = bool(cfg.enable_trailing) if cfg.enable_trailing is not None else True
    config["enable_time_exit"] = bool(cfg.enable_time_exit) if cfg.enable_time_exit is not None else True
    config["enable_partial_tp"] = bool(cfg.enable_partial_tp) if cfg.enable_partial_tp is not None else True
    config["max_daily_loss_pct"] = cfg.max_daily_loss_pct if cfg.max_daily_loss_pct is not None else 5.0
    config["max_total_loss_pct"] = cfg.max_total_loss_pct if cfg.max_total_loss_pct is not None else 10.0
    return config


def save_user_config(user_id: int, data: dict) -> dict:
    safe = {}
    if "symbols" in data:
        symbols = data["symbols"]
        if isinstance(symbols, list) and len(symbols) > 0:
            safe["symbols"] = json.dumps(symbols)
    for key in ["interval", "trade_quantity", "stop_loss_pct", "take_profit_pct",
                "max_position_size", "ma_fast_period", "ma_slow_period",
                "ml_confidence_threshold", "balance_allocation_pct",
                "ai_stop_loss_enabled", "ai_optimize_enabled",
                "trailing_stop_pct", "trailing_activation_pct", "time_exit_hours",
                "partial_tp1_pct", "partial_tp1_qty", "partial_tp2_pct", "partial_tp2_qty",
                "partial_tp3_pct", "partial_tp3_qty",
                "enable_trailing", "enable_time_exit", "enable_partial_tp",
                "max_daily_loss_pct", "max_total_loss_pct"]:
        if key in data:
            safe[key] = data[key]
    if safe:
        update_user_config(user_id, **safe)
    return load_user_config(user_id)