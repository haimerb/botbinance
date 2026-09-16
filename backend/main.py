import os
import asyncio
import pyotp
from fastapi import FastAPI, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator, model_validator
from binance.client import Client
from binance.exceptions import BinanceAPIException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.bot_runner import BotRunner
from backend.database import init_db, get_user_by_email, get_user_by_id, get_user_by_id_with_keys, add_user, update_binance_keys, get_trades, get_trade_stats, get_recent_trades, log_audit
from backend.auth import hash_password, verify_password, create_token_pair, get_current_user, decode_token, decode_refresh_token
from backend.user_config import load_user_config, save_user_config
from backend.security_headers import add_security_headers
from src.config import BINANCE_API_URL

init_db()

app = FastAPI(title="Binance Trading Bot API", version="1.0.0")

# API v1 Router
v1_router = APIRouter(prefix="/api/v1")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

add_security_headers(app)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

mock_mode = os.getenv("MOCK_MODE", "true").lower() == "true"
bot = BotRunner(mock_mode=mock_mode)

# Include v1 router
app.include_router(v1_router)

# Backward compatibility - also mount at /api (deprecated)
from fastapi import APIRouter as LegacyRouter
legacy_router = LegacyRouter(prefix="/api")
app.include_router(legacy_router)


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str
    mfa_code: str | None = None


class BinanceKeysRequest(BaseModel):
    api_key: str
    api_secret: str


def validate_password_complexity(password: str) -> str | None:
    if len(password) < 12:
        return "Contraseña debe tener al menos 12 caracteres"
    if not any(c.isupper() for c in password):
        return "Contraseña debe contener al menos una mayúscula"
    if not any(c.islower() for c in password):
        return "Contraseña debe contener al menos una minúscula"
    if not any(c.isdigit() for c in password):
        return "Contraseña debe contener al menos un número"
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return "Contraseña debe contener al menos un símbolo especial"
    return None


@app.post("/api/auth/register")
@limiter.limit("5/minute")
def register(request: Request, req: RegisterRequest):
    if not req.email or not req.password:
        raise HTTPException(status_code=400, detail="Email y contraseña requeridos")
    pwd_error = validate_password_complexity(req.password)
    if pwd_error:
        raise HTTPException(status_code=400, detail=pwd_error)
    existing = get_user_by_email(req.email)
    if existing:
        log_audit(
            user_id=None,
            event_type="register_failed",
            event_data=f"email={req.email}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(status_code=400, detail="Email ya registrado")
    user = add_user(req.email, hash_password(req.password))
    tokens = create_token_pair(user.id, user.email)
    log_audit(
        user_id=user.id,
        event_type="register_success",
        event_data=f"email={req.email}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"token": tokens["access_token"], "refresh_token": tokens["refresh_token"], "email": user.email, "user_id": user.id}


@app.post("/api/auth/login")
@limiter.limit("5/minute")
def login(request: Request, req: LoginRequest):
    user = get_user_by_email(req.email)
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    if not user or not verify_password(req.password, user.password_hash):
        log_audit(
            user_id=user.id if user else None,
            event_type="login_failed",
            event_data=f"email={req.email}",
            ip_address=ip,
            user_agent=ua,
        )
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    if user.mfa_enabled:
        if not req.mfa_code:
            raise HTTPException(status_code=400, detail="Código MFA requerido")
        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(req.mfa_code, valid_window=1):
            log_audit(
                user_id=user.id,
                event_type="login_mfa_failed",
                event_data=f"email={req.email}",
                ip_address=ip,
                user_agent=ua,
            )
            raise HTTPException(status_code=401, detail="Código MFA inválido")
    
    token = create_token_pair(user.id, user.email)
    log_audit(
        user_id=user.id,
        event_type="login_success",
        event_data=f"email={req.email}",
        ip_address=ip,
        user_agent=ua,
    )
    return {
        "token": token["access_token"],
        "refresh_token": token["refresh_token"],
        "email": user.email,
        "user_id": user.id,
        "has_binance_keys": bool(user.binance_api_key and user.binance_api_secret),
    }


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@app.post("/api/auth/refresh")
@limiter.limit("10/minute")
def refresh_token(request: Request, req: RefreshTokenRequest):
    try:
        payload = decode_refresh_token(req.refresh_token)
        user = get_user_by_id(payload["sub"])
        if not user:
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        tokens = create_token_pair(user.id, user.email)
        log_audit(
            user_id=user.id,
            event_type="token_refreshed",
            event_data=f"email={user.email}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return {
            "token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "bearer",
            "expires_in": tokens["expires_in"],
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Token de refresco inválido")


class MFASetupRequest(BaseModel):
    pass


class MFAVerifyRequest(BaseModel):
    code: str


class MFADisableRequest(BaseModel):
    password: str


@app.post("/api/auth/mfa/setup")
@limiter.limit("3/minute")
def mfa_setup(request: Request, current_user: dict = Depends(get_current_user)):
    import pyotp
    import qrcode
    import io
    import base64
    
    user = get_user_by_id(current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA ya está habilitado")
    
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    user.mfa_enabled = 0
    from backend.database import get_session
    with get_session() as session:
        session.merge(user)
    
    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=user.email, issuer_name="Binance Bot")
    
    qr = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    qr.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    
    log_audit(
        user_id=user.id,
        event_type="mfa_setup_initiated",
        event_data="",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    
    return {
        "secret": secret,
        "qr_code": f"data:image/png;base64,{qr_b64}",
        "uri": provisioning_uri,
    }


@app.post("/api/auth/mfa/verify")
@limiter.limit("5/minute")
def mfa_verify(request: Request, req: MFAVerifyRequest, current_user: dict = Depends(get_current_user)):
    import pyotp
    
    user = get_user_by_id(current_user["sub"])
    if not user or not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA no configurado")
    
    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA ya está habilitado")
    
    totp = pyotp.TOTP(user.mfa_secret)
    if not totp.verify(req.code, valid_window=1):
        log_audit(
            user_id=user.id,
            event_type="mfa_verify_failed",
            event_data="",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(status_code=400, detail="Código inválido")
    
    user.mfa_enabled = 1
    from backend.database import get_session
    with get_session() as session:
        session.merge(user)
    
    log_audit(
        user_id=user.id,
        event_type="mfa_enabled",
        event_data="",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    
    return {"status": "ok", "message": "MFA habilitado correctamente"}


@app.post("/api/auth/mfa/disable")
@limiter.limit("3/minute")
def mfa_disable(request: Request, req: MFADisableRequest, current_user: dict = Depends(get_current_user)):
    user = get_user_by_id(current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if not user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA no está habilitado")
    
    if not verify_password(req.password, user.password_hash):
        log_audit(
            user_id=user.id,
            event_type="mfa_disable_failed",
            event_data="invalid_password",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")
    
    user.mfa_enabled = 0
    user.mfa_secret = ""
    from backend.database import get_session
    with get_session() as session:
        session.merge(user)
    
    log_audit(
        user_id=user.id,
        event_type="mfa_disabled",
        event_data="",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    
    return {"status": "ok", "message": "MFA deshabilitado correctamente"}


@app.get("/api/auth/mfa/status")
def mfa_status(current_user: dict = Depends(get_current_user)):
    user = get_user_by_id(current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    return {
        "mfa_enabled": bool(user.mfa_enabled),
        "mfa_configured": bool(user.mfa_secret),
    }


@app.get("/api/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    user = get_user_by_id_with_keys(current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {
        "email": user.email,
        "user_id": user.id,
        "has_binance_keys": bool(user.binance_api_key and user.binance_api_secret),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@app.post("/api/auth/keys")
@limiter.limit("3/minute")
def save_binance_keys(
    request: Request,
    keys: BinanceKeysRequest,
    current_user: dict = Depends(get_current_user),
):
    try:
        client = Client(keys.api_key, keys.api_secret)
        client.API_URL = BINANCE_API_URL
        account = client.get_account()
        can_trade = account.get("canTrade", False)
        update_binance_keys(current_user["sub"], keys.api_key, keys.api_secret)
        log_audit(
            user_id=current_user["sub"],
            event_type="api_keys_updated",
            event_data="binance_keys_changed",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return {"status": "ok", "can_trade": can_trade}
    except BinanceAPIException as e:
        log_audit(
            user_id=current_user["sub"],
            event_type="api_keys_update_failed",
            event_data=f"error={e.message}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(status_code=400, detail=f"Error Binance: {e.message}")
    except Exception as e:
        log_audit(
            user_id=current_user["sub"],
            event_type="api_keys_update_failed",
            event_data=f"error={str(e)}",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        raise HTTPException(status_code=400, detail="Error al guardar keys")


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
    trailing_stop_pct: float | None = None
    trailing_activation_pct: float | None = None
    time_exit_hours: int | None = None
    partial_tp1_pct: float | None = None
    partial_tp1_qty: float | None = None
    partial_tp2_pct: float | None = None
    partial_tp2_qty: float | None = None
    partial_tp3_pct: float | None = None
    partial_tp3_qty: float | None = None
    enable_trailing: bool | None = None
    enable_time_exit: bool | None = None
    enable_partial_tp: bool | None = None
    max_daily_loss_pct: float | None = None
    max_total_loss_pct: float | None = None

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v):
        allowed = ["15m", "30m", "1h", "4h", "1d"]
        if v and v not in allowed:
            raise ValueError(f"Intervalo debe ser uno de: {allowed}")
        return v

    @field_validator("trade_quantity")
    @classmethod
    def validate_trade_quantity(cls, v):
        if v is not None and (v <= 0 or v > 100):
            raise ValueError("Cantidad por trade debe ser > 0 y <= 100")
        return v

    @field_validator("stop_loss_pct")
    @classmethod
    def validate_stop_loss(cls, v):
        if v is not None and (v <= 0 or v > 0.5):
            raise ValueError("Stop loss debe ser > 0% y <= 50%")
        return v

    @field_validator("take_profit_pct")
    @classmethod
    def validate_take_profit(cls, v):
        if v is not None and (v <= 0 or v > 1.0):
            raise ValueError("Take profit debe ser > 0% y <= 100%")
        return v

    @field_validator("max_position_size")
    @classmethod
    def validate_max_position(cls, v):
        if v is not None and (v <= 0 or v > 1.0):
            raise ValueError("Tamaño máx. posición debe ser > 0 y <= 100%")
        return v

    @field_validator("ma_fast_period", "ma_slow_period")
    @classmethod
    def validate_ma_periods(cls, v):
        if v is not None and (v < 2 or v > 500):
            raise ValueError("Período MA debe ser >= 2 y <= 500")
        return v

    @field_validator("ml_confidence_threshold")
    @classmethod
    def validate_ml_confidence(cls, v):
        if v is not None and (v < 0.01 or v > 0.99):
            raise ValueError("Confianza ML debe ser entre 1% y 99%")
        return v

    @field_validator("balance_allocation_pct")
    @classmethod
    def validate_balance_allocation(cls, v):
        if v is not None and (v < 1 or v > 100):
            raise ValueError("Balance asignado debe ser entre 1% y 100%")
        return v

    @field_validator("trailing_stop_pct", "trailing_activation_pct")
    @classmethod
    def validate_trailing(cls, v):
        if v is not None and (v <= 0 or v > 0.5):
            raise ValueError("Trailing debe ser > 0% y <= 50%")
        return v

    @field_validator("time_exit_hours")
    @classmethod
    def validate_time_exit(cls, v):
        if v is not None and (v < 0 or v > 168):
            raise ValueError("Time exit debe ser entre 0 y 168 horas")
        return v

    @field_validator("partial_tp1_pct", "partial_tp2_pct", "partial_tp3_pct")
    @classmethod
    def validate_partial_tp_pct(cls, v):
        if v is not None and (v <= 0 or v > 1.0):
            raise ValueError("Partial TP % debe ser > 0% y <= 100%")
        return v

    @field_validator("partial_tp1_qty", "partial_tp2_qty", "partial_tp3_qty")
    @classmethod
    def validate_partial_tp_qty(cls, v):
        if v is not None and (v <= 0 or v > 1.0):
            raise ValueError("Partial TP qty debe ser > 0% y <= 100%")
        return v

    @field_validator("max_daily_loss_pct", "max_total_loss_pct")
    @classmethod
    def validate_circuit_breaker(cls, v):
        if v is not None and (v < 0.1 or v > 50.0):
            raise ValueError("Límite de pérdida debe ser entre 0.1% y 50%")
        return v

    @model_validator(mode="after")
    def validate_ma_order(self):
        if self.ma_fast_period and self.ma_slow_period:
            if self.ma_fast_period >= self.ma_slow_period:
                raise ValueError("MA rápido debe ser menor que MA lento")
        return self


@app.get("/api/user/config")
def get_user_config(current_user: dict = Depends(get_current_user)):
    return load_user_config(current_user["sub"])


@app.put("/api/user/config")
def update_user_config_endpoint(
    request: Request,
    req: UserConfigUpdate,
    current_user: dict = Depends(get_current_user),
):
    data = {k: v for k, v in req.model_dump().items() if v is not None}
    result = save_user_config(current_user["sub"], data)
    log_audit(
        user_id=current_user["sub"],
        event_type="config_updated",
        event_data=f"fields={list(data.keys())}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return result


@app.get("/api/user/profile")
def get_user_profile(current_user: dict = Depends(get_current_user)):
    user = get_user_by_id_with_keys(current_user["sub"])
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
def start_bot(request: Request, current_user: dict = Depends(get_current_user)):
    user = get_user_by_id_with_keys(current_user["sub"])
    bot.set_user(current_user["sub"])
    if not mock_mode and (not user.binance_api_key or not user.binance_api_secret):
        raise HTTPException(status_code=400, detail="Configura tus API keys de Binance primero")
    bot.start()
    log_audit(
        user_id=current_user["sub"],
        event_type="bot_started",
        event_data=f"mock_mode={mock_mode}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"status": "started"}


@app.post("/api/stop")
def stop_bot(request: Request, current_user: dict = Depends(get_current_user)):
    bot.set_user(current_user["sub"])
    bot.stop()
    log_audit(
        user_id=current_user["sub"],
        event_type="bot_stopped",
        event_data="",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
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


@app.websocket("/api/ws")
async def websocket_endpoint(ws: WebSocket):
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Token requerido")
        return
    try:
        current_user = decode_token(token)
    except HTTPException:
        await ws.close(code=4001, reason="Token inválido")
        return
    
    bot.set_user(current_user["sub"])
    await ws.accept()
    try:
        while True:
            state = bot.get_state()
            await ws.send_json(state)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


@app.get("/api/config/suggest")
def suggest_config(current_user: dict = Depends(get_current_user)):
    bot.set_user(current_user["sub"])
    state = bot.get_state()
    prices = state.get("current_prices", {})
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
        vol = state.get("signals", {}).get("volatility", "LOW")
        if vol == "HIGH":
            suggestions["stop_loss_pct"] = round(max(atr_ratio * 2, 0.02), 3)
            suggestions["take_profit_pct"] = round(max(atr_ratio * 4, 0.03), 3)
    return {"suggestions": suggestions, "market": "analyzed"}
