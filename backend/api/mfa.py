import base64
import io

import pyotp
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Request

from backend.core.config import limiter
from backend.core.deps import get_current_user
from backend.services.auth import verify_password
from backend.services.database import get_user_by_id, log_audit, get_session
from backend.schemas import MFAVerifyRequest, MFADisableRequest

router = APIRouter(prefix="/api/auth/mfa", tags=["auth"])


def _client_meta(request: Request) -> dict:
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


def _security_alert(event_type: str, detail: str, request: Request):
    try:
        from backend.services.notifications import notify_security_alert
        notify_security_alert(
            event_type,
            detail,
            request.client.host if request.client else None,
        )
    except Exception:
        pass


@router.post("/setup")
@limiter.limit("3/minute")
def mfa_setup(request: Request, current_user: dict = Depends(get_current_user)):
    user = get_user_by_id(current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA ya está habilitado")

    secret = pyotp.random_base32()
    user.mfa_secret = secret
    user.mfa_enabled = 0
    with get_session() as session:
        session.merge(user)

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(name=user.email, issuer_name="Binance Bot")

    qr = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    log_audit(
        user_id=user.id,
        event_type="mfa_setup_initiated",
        event_data="",
        **_client_meta(request),
    )

    return {
        "secret": secret,
        "qr_code": f"data:image/png;base64,{qr_b64}",
        "uri": provisioning_uri,
    }


@router.post("/verify")
@limiter.limit("5/minute")
def mfa_verify(
    request: Request,
    req: MFAVerifyRequest,
    current_user: dict = Depends(get_current_user),
):
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
            **_client_meta(request),
        )
        raise HTTPException(status_code=400, detail="Código inválido")

    user.mfa_enabled = 1
    with get_session() as session:
        session.merge(user)

    log_audit(
        user_id=user.id,
        event_type="mfa_enabled",
        event_data="",
        **_client_meta(request),
    )

    return {"status": "ok", "message": "MFA habilitado correctamente"}


@router.post("/disable")
@limiter.limit("3/minute")
def mfa_disable(
    request: Request,
    req: MFADisableRequest,
    current_user: dict = Depends(get_current_user),
):
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
            **_client_meta(request),
        )
        raise HTTPException(status_code=401, detail="Contraseña incorrecta")

    user.mfa_enabled = 0
    user.mfa_secret = ""
    with get_session() as session:
        session.merge(user)

    log_audit(
        user_id=user.id,
        event_type="mfa_disabled",
        event_data="",
        **_client_meta(request),
    )

    _security_alert("mfa_disabled", f"user_id={user.id}", request)

    return {"status": "ok", "message": "MFA deshabilitado correctamente"}


@router.get("/status")
def mfa_status(current_user: dict = Depends(get_current_user)):
    user = get_user_by_id(current_user["sub"])
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return {
        "mfa_enabled": bool(user.mfa_enabled),
        "mfa_configured": bool(user.mfa_secret),
    }
