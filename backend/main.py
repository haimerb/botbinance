import time

from fastapi import FastAPI, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from backend.core.config import MOCK_MODE, ALLOWED_ORIGINS, limiter
from backend.core.security_headers import add_security_headers
from backend.services.database import init_db
from backend.services.metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_DURATION
from backend.api import auth, mfa, bot, trades, market, user, alerts, ws, health, backtest

init_db()

app = FastAPI(title="Binance Trading Bot API", version="1.0.0")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

add_security_headers(app)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    HTTP_REQUESTS_TOTAL.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).inc()
    HTTP_REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path,
    ).observe(duration)
    return response


# Compatibilidad hacia atrás: parámetros heredados montados bajo /api
v1_router = APIRouter(prefix="/api/v1")
app.include_router(v1_router)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(mfa.router)
app.include_router(bot.router)
app.include_router(trades.router)
app.include_router(market.router)
app.include_router(backtest.router)
app.include_router(user.router)
app.include_router(alerts.router)
app.include_router(ws.router)
