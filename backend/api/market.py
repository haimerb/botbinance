from fastapi import APIRouter, Depends, HTTPException, Query

from backend.core.deps import get_current_user

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/klines")
def get_klines_api(
    current_user: dict = Depends(get_current_user),
    symbol: str = Query("BTCUSDT"),
    interval: str = Query("1h"),
    limit: int = Query(200, ge=10, le=1000),
):
    from src.data.binance_client import BinanceDataClient

    symbol = symbol.upper()
    if not symbol.endswith(("USDT", "BUSD", "USDC")):
        symbol = symbol + "USDT"
    allowed = {"1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"}
    if interval not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Intervalo inválido. Permitidos: {sorted(allowed)}",
        )

    try:
        client = BinanceDataClient()
        df = client.fetch_klines(symbol, interval, limit=limit, use_real_api=True)
        if df is None or df.empty:
            df = client.fetch_klines(symbol, interval, limit=limit, use_real_api=False)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error obteniendo velas: {e}")

    if df is None or df.empty:
        return {"symbol": symbol, "interval": interval, "klines": []}

    candles = []
    for _, row in df.iterrows():
        candles.append({
            "time": str(row.get("timestamp", "")),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row.get("volume", 0) or 0),
        })
    return {"symbol": symbol, "interval": interval, "klines": candles}
