from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

# App info
APP_INFO = Info('botbinance_app', 'BotBinance application info')
APP_INFO.info({'version': '1.0.0', 'environment': 'paper-trading'})

# HTTP metrics
HTTP_REQUESTS_TOTAL = Counter(
    'botbinance_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

HTTP_REQUEST_DURATION = Histogram(
    'botbinance_http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Auth metrics
AUTH_LOGIN_TOTAL = Counter(
    'botbinance_auth_login_total',
    'Total login attempts',
    ['status']  # success, failed
)

AUTH_MFA_VERIFIED = Counter(
    'botbinance_auth_mfa_verified_total',
    'Total MFA verifications',
    ['status']  # success, failed
)

AUTH_TOKEN_REFRESH = Counter(
    'botbinance_auth_token_refresh_total',
    'Total token refresh attempts',
    ['status']  # success, failed
)

# Bot metrics
BOT_STATUS = Gauge(
    'botbinance_bot_status',
    'Bot status (1=running, 0=stopped, -1=error)',
    ['status']
)

BOT_PNL_USD = Gauge(
    'botbinance_total_pnl_usd',
    'Total P&L in USD'
)

BOT_PNL_BY_SYMBOL = Gauge(
    'botbinance_pnl_by_symbol',
    'P&L by symbol in USD',
    ['symbol']
)

BOT_DAILY_LOSS_PCT = Gauge(
    'botbinance_daily_loss_pct',
    'Daily loss percentage'
)

BOT_TOTAL_LOSS_PCT = Gauge(
    'botbinance_total_loss_pct',
    'Total loss percentage'
)

BOT_ACTIVE_POSITIONS = Gauge(
    'botbinance_active_positions',
    'Number of active positions'
)

BOT_CIRCUIT_BREAKER_TRIGGERED = Counter(
    'botbinance_circuit_breaker_triggered_total',
    'Circuit breaker triggered count',
    ['type']  # daily, total
)

# Trading metrics
TRADES_EXECUTED = Counter(
    'botbinance_trades_executed_total',
    'Total trades executed',
    ['symbol', 'side', 'status']  # status: filled, rejected, partial
)

SIGNALS_GENERATED = Counter(
    'botbinance_signals_generated_total',
    'Total signals generated',
    ['symbol', 'signal']  # BUY, SELL, HOLD
)

# ML metrics
ML_PREDICTIONS = Counter(
    'botbinance_ml_predictions_total',
    'Total ML predictions',
    ['symbol', 'prediction']  # BUY, SELL, HOLD
)

ML_MODEL_ERRORS = Counter(
    'botbinance_ml_model_errors_total',
    'Total ML model errors',
    ['error_type']
)

ML_MODEL_LOAD_TIME = Histogram(
    'botbinance_ml_model_load_duration_seconds',
    'ML model load time',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# Binance connection metrics
TRADE_EXECUTOR_CONNECTED = Gauge(
    'botbinance_trade_executor_connected',
    'Trade executor connection status (1=connected, 0=disconnected)'
)

DATA_CLIENT_CONNECTED = Gauge(
    'botbinance_data_client_connected',
    'Data client connection status (1=connected, 0=disconnected)'
)

# WebSocket metrics
WS_CONNECTIONS_ACTIVE = Gauge(
    'botbinance_ws_connections_active',
    'Active WebSocket connections'
)

WS_RECONNECT_TOTAL = Counter(
    'botbinance_ws_reconnect_total',
    'Total WebSocket reconnections'
)

WS_MESSAGES_SENT = Counter(
    'botbinance_ws_messages_sent_total',
    'Total WebSocket messages sent'
)

# System metrics
CPU_USAGE = Gauge(
    'botbinance_cpu_usage_percent',
    'CPU usage percentage'
)

MEMORY_USAGE = Gauge(
    'botbinance_memory_usage_percent',
    'Memory usage percentage'
)

DB_CONNECTIONS_ACTIVE = Gauge(
    'botbinance_db_connections_active',
    'Active database connections'
)

DB_QUERY_DURATION = Histogram(
    'botbinance_db_query_duration_seconds',
    'Database query duration',
    ['query_type'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

# Risk metrics
RISK_POSITION_SIZE = Gauge(
    'botbinance_risk_position_size_usd',
    'Position size in USD',
    ['symbol']
)

RISK_STOP_LOSS_DISTANCE = Gauge(
    'botbinance_risk_stop_loss_distance_pct',
    'Stop loss distance percentage',
    ['symbol']
)

RISK_TAKE_PROFIT_DISTANCE = Gauge(
    'botbinance_risk_take_profit_distance_pct',
    'Take profit distance percentage',
    ['symbol']
)


def update_bot_status(status: str):
    """Update bot status gauge."""
    status_map = {'running': 1, 'stopped': 0, 'error': -1, 'circuit_breaker': -1}
    BOT_STATUS.labels(status=status).set(status_map.get(status, 0))


def update_pnl(total_usd: float, by_symbol: dict = None):
    """Update P&L metrics."""
    BOT_PNL_USD.set(total_usd)
    if by_symbol:
        for symbol, pnl in by_symbol.items():
            BOT_PNL_BY_SYMBOL.labels(symbol=symbol).set(pnl)


def update_circuit_breaker(daily_pct: float, total_pct: float):
    """Update circuit breaker metrics."""
    BOT_DAILY_LOSS_PCT.set(daily_pct)
    BOT_TOTAL_LOSS_PCT.set(total_pct)


def record_trade(symbol: str, side: str, status: str):
    """Record a trade execution."""
    TRADES_EXECUTED.labels(symbol=symbol, side=side, status=status).inc()


def record_signal(symbol: str, signal: str):
    """Record a signal generation."""
    SIGNALS_GENERATED.labels(symbol=symbol, signal=signal).inc()


def record_ml_prediction(symbol: str, prediction: str):
    """Record ML prediction."""
    ML_PREDICTIONS.labels(symbol=symbol, prediction=prediction).inc()


def record_ml_error(error_type: str):
    """Record ML model error."""
    ML_MODEL_ERRORS.labels(error_type=error_type).inc()


def set_binance_connections(trade_executor: bool, data_client: bool):
    """Set Binance connection status."""
    TRADE_EXECUTOR_CONNECTED.set(1 if trade_executor else 0)
    DATA_CLIENT_CONNECTED.set(1 if data_client else 0)


def update_ws_connections(active: int, reconnects: int = 0):
    """Update WebSocket metrics."""
    WS_CONNECTIONS_ACTIVE.set(active)
    if reconnects:
        WS_RECONNECT_TOTAL.inc(reconnects)


def record_ws_message():
    """Record WebSocket message sent."""
    WS_MESSAGES_SENT.inc()


def update_system_metrics(cpu_pct: float, memory_pct: float):
    """Update system metrics."""
    CPU_USAGE.set(cpu_pct)
    MEMORY_USAGE.set(memory_pct)


def update_db_connections(active: int):
    """Update database connection count."""
    DB_CONNECTIONS_ACTIVE.set(active)


def record_db_query(query_type: str, duration: float):
    """Record database query duration."""
    DB_QUERY_DURATION.labels(query_type=query_type).observe(duration)


def update_risk_metrics(symbol: str, position_usd: float, sl_pct: float, tp_pct: float):
    """Update risk metrics."""
    RISK_POSITION_SIZE.labels(symbol=symbol).set(position_usd)
    RISK_STOP_LOSS_DISTANCE.labels(symbol=symbol).set(sl_pct)
    RISK_TAKE_PROFIT_DISTANCE.labels(symbol=symbol).set(tp_pct)


def metrics_endpoint():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)