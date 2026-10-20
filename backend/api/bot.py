from fastapi import APIRouter, Depends, HTTPException, Request

from backend.core.config import bot, MOCK_MODE
from backend.core.deps import get_current_user
from backend.services.database import get_user_by_id_with_keys, log_audit
from backend.services.user_config import load_user_config
from backend.services.metrics import update_bot_status

router = APIRouter(prefix="/api", tags=["bot"])


@router.get("/status")
def get_status(current_user: dict = Depends(get_current_user)):
    bot.set_user(current_user["sub"])
    return bot.get_state()


@router.post("/start")
def start_bot(request: Request, current_user: dict = Depends(get_current_user)):
    user = get_user_by_id_with_keys(current_user["sub"])
    bot.set_user(current_user["sub"])
    if not MOCK_MODE and (not user.binance_api_key or not user.binance_api_secret):
        raise HTTPException(
            status_code=400, detail="Configura tus API keys de Binance primero"
        )
    bot.start()
    update_bot_status("running")
    log_audit(
        user_id=current_user["sub"],
        event_type="bot_started",
        event_data=f"mock_mode={MOCK_MODE}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"status": "started"}


@router.post("/stop")
def stop_bot(request: Request, current_user: dict = Depends(get_current_user)):
    bot.set_user(current_user["sub"])
    bot.stop()
    update_bot_status("stopped")
    log_audit(
        user_id=current_user["sub"],
        event_type="bot_stopped",
        event_data="",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"status": "stopped"}


@router.get("/config/suggest")
def suggest_config(current_user: dict = Depends(get_current_user)):
    bot.set_user(current_user["sub"])
    state = bot.get_state()
    prices = state.get("current_prices", {})
    suggestions = {}
    first_price = None
    for _sym, price in prices.items():
        if price and price > 0:
            first_price = price
            break
    if first_price and first_price > 0:
        atr_ratio = 0.02
        suggestions["stop_loss_pct"] = round(min(max(atr_ratio * 1.5, 0.01), 0.05), 3)
        suggestions["take_profit_pct"] = round(min(max(atr_ratio * 3, 0.02), 0.08), 3)
        if first_price > 10000:
            suggestions["trade_quantity"] = 0.001
        elif first_price > 1000:
            suggestions["trade_quantity"] = 0.01
        else:
            suggestions["trade_quantity"] = 1.0
        suggestions["ma_fast_period"] = 9
        suggestions["ma_slow_period"] = 21
        vol = state.get("signals", {}).get("volatility", "LOW")
        if vol == "HIGH":
            suggestions["stop_loss_pct"] = round(max(atr_ratio * 2, 0.02), 3)
            suggestions["take_profit_pct"] = round(max(atr_ratio * 4, 0.03), 3)
    return {"suggestions": suggestions, "market": "analyzed"}
