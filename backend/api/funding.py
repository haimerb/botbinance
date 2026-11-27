from fastapi import APIRouter, Depends, HTTPException, Request

from backend.core.config import MOCK_MODE, funding_runner
from backend.core.deps import get_current_user
from backend.services.database import get_user_by_id_with_keys, log_audit

router = APIRouter(prefix="/api/funding", tags=["funding"])


@router.get("/status")
def funding_status(current_user: dict = Depends(get_current_user)):
    return funding_runner.get_state()


@router.get("/opportunities")
def funding_opportunities(current_user: dict = Depends(get_current_user)):
    return {"opportunities": funding_runner.get_state()["opportunities"]}


@router.post("/start")
def start_funding(request: Request, current_user: dict = Depends(get_current_user)):
    user = get_user_by_id_with_keys(current_user["sub"])
    if not MOCK_MODE and (not user.binance_api_key or not user.binance_api_secret):
        raise HTTPException(
            status_code=400, detail="Configura tus API keys de Binance primero"
        )
    funding_runner.configure(
        api_key=user.binance_api_key,
        api_secret=user.binance_api_secret,
    )
    funding_runner.start()
    log_audit(
        user_id=current_user["sub"],
        event_type="funding_started",
        event_data=f"mock_mode={MOCK_MODE}",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"status": "started"}


@router.post("/stop")
def stop_funding(request: Request, current_user: dict = Depends(get_current_user)):
    funding_runner.stop()
    log_audit(
        user_id=current_user["sub"],
        event_type="funding_stopped",
        event_data="",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return {"status": "stopped"}
