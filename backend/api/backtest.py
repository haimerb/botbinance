from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.deps import get_current_user

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("")
def run_backtest(
    current_user: dict = Depends(get_current_user),
    symbol: str = Query("BTCUSDT"),
    interval: str = Query("1h"),
    limit: int = Query(1000, ge=100, le=5000),
):
    symbol = symbol.upper()
    if not symbol.endswith(("USDT", "BUSD", "USDC")):
        symbol = symbol + "USDT"
    allowed = {"15m", "30m", "1h", "4h", "1d"}
    if interval not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Intervalo inválido. Permitidos: {sorted(allowed)}",
        )

    from backend.workers.tasks import backtest_symbol

    try:
        task = backtest_symbol.delay(current_user["sub"], symbol, interval, limit)
        return {"status": "queued", "task_id": task.id, "symbol": symbol, "interval": interval}
    except Exception:
        result = backtest_symbol(current_user["sub"], symbol, interval, limit)
        return {"status": result.get("status", "ok"), "symbol": symbol,
                "interval": interval, "result": result.get("result"), "detail": result.get("detail")}
