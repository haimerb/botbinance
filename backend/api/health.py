import os

from fastapi import APIRouter, HTTPException

from backend.services.metrics import metrics_endpoint

router = APIRouter(tags=["health"])


@router.get("/metrics")
def metrics():
    return metrics_endpoint()


@router.get("/health")
def health_check():
    from sqlalchemy import text
    from backend.services.database import engine

    checks = {"api": "ok"}
    status_code = 200
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        status_code = 503
    try:
        import redis

        r = redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            socket_connect_timeout=2,
        )
        r.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "unavailable"
    if status_code != 200:
        raise HTTPException(status_code=status_code, detail=checks)
    return checks
