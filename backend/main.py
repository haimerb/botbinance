import os
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from binance.client import Client
from binance.exceptions import BinanceAPIException

from backend.bot_runner import BotRunner
from backend.database import init_db, get_user_by_email, get_user_by_id, add_user, update_binance_keys, get_trades, get_trade_stats, get_recent_trades
from backend.auth import hash_password, verify_password, create_token, get_current_user
from backend.user_config import load_user_config, save_user_config

init_db()

app = FastAPI(title="Binance Trading Bot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mock_mode = os.getenv("MOCK_MODE", "true").lower() == "true"
bot = BotRunner(mock_mode=mock_mode)


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class BinanceKeysRequest(BaseModel):
    api_key: str
    api_secret: str


@app.post("/api/auth/register")
def register(req: RegisterRequest):
    if not req.email or not req.password:
        raise HTTPException(status_code=400, detail="Email y contraseña requeridos")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Contraseña debe tener al menos 6 caracteres")
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email ya registrado")
    user = add_user(req.email, hash_password(req.password))
    token = create_token(user.id, user.email)
    return {"token": token, "email": user.email, "user_id": user.id}


@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    token = create_token(user.id, user.email)
    return {
        "token": token,
        "email": user.email,
        "user_id": user.id,
        "has_binance_keys": bool(user.binance_api_key and user.binance_api_secret),
    }


@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    user = get_user_by_id(current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {
        "email": user.email,
        "user_id": user.id,
        "has_binance_keys": bool(user.binance_api_key and user.binance_api_secret),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@app.post("/api/auth/keys")
def save_binance_keys(
    keys: BinanceKeysRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        client = Client(keys.api_key, keys.api_secret)
        if mock_mode:
            client.API_URL = "https://testnet.binance.vision/api"
        account = client.get_account()
        can_trade = account.get("canTrade", False)
        update_binance_keys(current_user["sub"], keys.api_key, keys.api_secret)
        return {"status": "ok", "can_trade": can_trade}
    except BinanceAPIException as e:
        raise HTTPException(status_code=400, detail=f"Error Binance: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")


class UserConfigUpdate(BaseModel):
    symbols: list[str] | None = None
    interval: str | None = None
    trade_quantity: float | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    max_position_size: float | None = None
    ma_fast_period: int | None = None
    ma_slow_period: int | None = None
    ml_confidence_threshold: float | None = None
    balance_allocation_pct: float | None = None
    ai_stop_loss_enabled: bool | None = None
    ai_optimize_enabled: bool | None = None


@app.get("/api/user/config")
def get_user_config(current_user: dict = Depends(get_current_user)):
    return load_user_config(current_user["sub"])


@app.put("/api/user/config")
def update_user_config_endpoint(
    req: UserConfigUpdate,
    current_user: dict = Depends(get_current_user),
):
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    return save_user_config(current_user["sub"], data)


@app.get("/api/user/profile")
def get_user_profile(current_user: dict = Depends(get_current_user)):
    user = get_user_by_id(current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {
        "email": user.email,
        "user_id": user.id,
        "has_binance_keys": bool(user.binance_api_key and user.binance_api_secret),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "config": load_user_config(current_user["sub"]),
    }


@app.get("/api/status")
def get_status(current_user: dict = Depends(get_current_user)):
    bot.set_user(current_user["sub"])
    return bot.get_state()


@app.post("/api/start")
def start_bot(current_user: dict = Depends(get_current_user)):
    user = get_user_by_id(current_user["sub"])
    bot.set_user(current_user["sub"])
    if not mock_mode and (not user.binance_api_key or not user.binance_api_secret):
        raise HTTPException(status_code=400, detail="Configura tus API keys de Binance primero")
    bot.start()
    return {"status": "started"}


@app.post("/api/stop")
def stop_bot(current_user: dict = Depends(get_current_user)):
    bot.set_user(current_user["sub"])
    bot.stop()
    return {"status": "stopped"}


@app.get("/api/trades")
def get_trades_api(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
):
    return {"trades": get_trades(current_user["sub"], limit)}


@app.get("/api/trades/stats")
def get_trades_stats_api(current_user: dict = Depends(get_current_user)):
    return get_trade_stats(current_user["sub"])


@app.get("/api/trades/recent")
def get_recent_trades_api(
    current_user: dict = Depends(get_current_user),
    since_id: int = Query(0, ge=0),
):
    return {"trades": get_recent_trades(current_user["sub"], since_id), "since_id": since_id}


@app.get("/api/config/suggest")
def suggest_config(current_user: dict = Depends(get_current_user)):
    bot.set_user(current_user["sub"])
    prices = bot.state.get("current_prices", {})
    cfg = load_user_config(current_user["sub"])
    suggestions = {}
    first_price = None
    for sym, price in prices.items():
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
        vol = bot.state.get("signals", {}).get("volatility", "LOW")
        if vol == "HIGH":
            suggestions["stop_loss_pct"] = round(max(atr_ratio * 2, 0.02), 3)
            suggestions["take_profit_pct"] = round(max(atr_ratio * 4, 0.03), 3)
    return {"suggestions": suggestions, "market": "analyzed"}
