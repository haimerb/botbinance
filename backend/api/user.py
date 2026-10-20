from fastapi import APIRouter, Depends, HTTPException, Request

from backend.core.deps import get_current_user
from backend.services.database import get_user_by_id_with_keys, log_audit
from backend.services.user_config import load_user_config, save_user_config
from backend.schemas import UserConfigUpdate

router = APIRouter(prefix="/api/user", tags=["user"])


@router.get("/config")
def get_user_config(current_user: dict = Depends(get_current_user)):
    return load_user_config(current_user["sub"])


@router.put("/config")
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


@router.get("/profile")
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
