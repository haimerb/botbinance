from fastapi import APIRouter, Depends, Query

from backend.core.deps import get_current_user
from backend.services.database import get_trades, get_trade_stats, get_recent_trades

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("")
def get_trades_api(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=500),
):
    return {"trades": get_trades(current_user["sub"], limit)}


@router.get("/stats")
def get_trades_stats_api(current_user: dict = Depends(get_current_user)):
    return get_trade_stats(current_user["sub"])


@router.get("/recent")
def get_recent_trades_api(
    current_user: dict = Depends(get_current_user),
    since_id: int = Query(0, ge=0),
):
    return {
        "trades": get_recent_trades(current_user["sub"], since_id),
        "since_id": since_id,
    }
