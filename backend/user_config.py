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
}


def load_user_config(user_id: int) -> dict:
    cfg = get_or_create_user_config(user_id)
    config = dict(DEFAULTS)
    config["symbols"] = json.loads(cfg.symbols) if cfg.symbols else list(DEFAULT_SYMBOLS)
    config["interval"] = cfg.interval or INTERVAL
    config["trade_quantity"] = cfg.trade_quantity or TRADE_QUANTITY
    config["stop_loss_pct"] = cfg.stop_loss_pct or STOP_LOSS_PCT
    config["take_profit_pct"] = cfg.take_profit_pct or TAKE_PROFIT_PCT
    config["max_position_size"] = cfg.max_position_size or MAX_POSITION_SIZE
    config["ma_fast_period"] = cfg.ma_fast_period or MA_FAST_PERIOD
    config["ma_slow_period"] = cfg.ma_slow_period or MA_SLOW_PERIOD
    config["ml_confidence_threshold"] = cfg.ml_confidence_threshold or ML_CONFIDENCE_THRESHOLD
    config["balance_allocation_pct"] = cfg.balance_allocation_pct if cfg.balance_allocation_pct is not None else BALANCE_ALLOCATION_PCT
    config["ai_stop_loss_enabled"] = bool(cfg.ai_stop_loss_enabled) if cfg.ai_stop_loss_enabled is not None else False
    config["ai_optimize_enabled"] = bool(cfg.ai_optimize_enabled) if cfg.ai_optimize_enabled is not None else False
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
                "ai_stop_loss_enabled", "ai_optimize_enabled"]:
        if key in data:
            safe[key] = data[key]
    if safe:
        update_user_config(user_id, **safe)
    return load_user_config(user_id)