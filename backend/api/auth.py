import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.core.config import limiter
from backend.services.auth import (
    hash_password,
    verify_password,
    create_token_pair,
    get_current_user,
    decode_refresh_token,
)
from backend.services.database import (
    get_user_by_email,
    get_user_by_id,
    get_user_by_id_with_keys,
    add_user,
    update_binance_keys,
    log_audit,
)
from backend.services.metrics import (
    AUTH_LOGIN_TOTAL,
    AUTH_MFA_VERIFIED,
    AUTH_TOKEN_REFRESH,
)
from backend.schemas import (
    RegisterRequest,
    LoginRequest,
    RefreshTokenRequest,
    BinanceKeysRequest,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_meta(request: Request) -> dict:
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


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


@router.post("/register")
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
            **_client_meta(request),
        )
        raise HTTPException(status_code=400, detail="Email ya registrado")
    user = add_user(req.email, hash_password(req.password))
    tokens = create_token_pair(user.id, user.email)
    log_audit(
        user_id=user.id,
        event_type="register_success",
        event_data=f"email={req.email}",
        **_client_meta(request),
    )
    return {
        "token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "email": user.email,
        "user_id": user.id,
    }


@router.post("/login")
@limiter.limit("5/minute")
def login(request: Request, req: LoginRequest):
    user = get_user_by_email(req.email)
    meta = _client_meta(request)
    if not user or not verify_password(req.password, user.password_hash):
        log_audit(
            user_id=user.id if user else None,
            event_type="login_failed",
            event_data=f"email={req.email}",
            **meta,
        )
        AUTH_LOGIN_TOTAL.labels(status="failed").inc()
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
                **meta,
            )
            raise HTTPException(status_code=401, detail="Código MFA inválido")
        AUTH_MFA_VERIFIED.labels(status="success").inc()

    token = create_token_pair(user.id, user.email)
    log_audit(
        user_id=user.id,
        event_type="login_success",
        event_data=f"email={req.email}",
        **meta,
    )
    AUTH_LOGIN_TOTAL.labels(status="success").inc()
    return {
        "token": token["access_token"],
        "refresh_token": token["refresh_token"],
        "email": user.email,
        "user_id": user.id,
        "has_binance_keys": bool(user.binance_api_key and user.binance_api_secret),
    }


@router.post("/refresh")
@limiter.limit("10/minute")
def refresh_token(request: Request, req: RefreshTokenRequest):
    try:
        payload = decode_refresh_token(req.refresh_token)
        user = get_user_by_id(payload["sub"])
        if not user:
            AUTH_TOKEN_REFRESH.labels(status="failed").inc()
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        tokens = create_token_pair(user.id, user.email)
        log_audit(
            user_id=user.id,
            event_type="token_refreshed",
            event_data=f"email={user.email}",
            **_client_meta(request),
        )
        AUTH_TOKEN_REFRESH.labels(status="success").inc()
        return {
            "token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": "bearer",
            "expires_in": tokens["expires_in"],
        }
    except HTTPException:
        raise
    except Exception:
        AUTH_TOKEN_REFRESH.labels(status="failed").inc()
        raise HTTPException(status_code=401, detail="Token de refresco inválido")


@router.get("/me")
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


@router.post("/keys")
@limiter.limit("3/minute")
def save_binance_keys(
    request: Request,
    keys: BinanceKeysRequest,
    current_user: dict = Depends(get_current_user),
):
    from binance.client import Client
    from binance.exceptions import BinanceAPIException
    from src.config import BINANCE_API_URL

    meta = _client_meta(request)
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
            **meta,
        )
        return {"status": "ok", "can_trade": can_trade}
    except BinanceAPIException as e:
        log_audit(
            user_id=current_user["sub"],
            event_type="api_keys_update_failed",
            event_data=f"error={e.message}",
            **meta,
        )
        raise HTTPException(status_code=400, detail=f"Error Binance: {e.message}")
    except Exception as e:
        log_audit(
            user_id=current_user["sub"],
            event_type="api_keys_update_failed",
            event_data=f"error={str(e)}",
            **meta,
        )
        raise HTTPException(status_code=400, detail="Error al guardar keys")
