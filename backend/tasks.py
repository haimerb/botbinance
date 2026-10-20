import os
from datetime import datetime, timedelta

from backend.celery_app import celery_app


@celery_app.task(name="backend.tasks.cleanup_old_logs")
def cleanup_old_logs():
    """Elimina logs de auditoría y errores más antiguos que la retención configurada."""
    from backend.database import get_session, AuditLog, ErrorLog
    from sqlalchemy import text

    retention_days = int(os.getenv("LOG_RETENTION_DAYS", "90"))
    cutoff = datetime.now() - timedelta(days=retention_days)

    deleted_audit = 0
    deleted_errors = 0
    with get_session() as session:
        result = session.query(AuditLog).filter(AuditLog.timestamp < cutoff).delete()
        deleted_audit = result or 0
        result = session.query(ErrorLog).filter(ErrorLog.timestamp < cutoff).delete()
        deleted_errors = result or 0

    return {
        "status": "ok",
        "deleted_audit_logs": deleted_audit,
        "deleted_error_logs": deleted_errors,
        "retention_days": retention_days,
    }


@celery_app.task(name="backend.tasks.send_daily_report")
def send_daily_report():
    """Envía reporte diario de P&L de todos los usuarios activos."""
    from backend.database import get_session, User, Trade
    from backend.notifications import notify_daily_report
    from sqlalchemy import func

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    reports_sent = 0

    with get_session() as session:
        users = session.query(User).all()
        for user in users:
            trades = session.query(Trade).filter(
                Trade.user_id == user.id,
                Trade.timestamp >= today_start,
            ).all()
            if not trades:
                continue
            total_pnl = sum(t.pnl_pct or 0 for t in trades if t.trade_type in ("exit", "stop_loss", "take_profit"))
            wins = len([t for t in trades if (t.pnl_pct or 0) >= 0 and t.pnl_pct is not None])
            notify_daily_report(user.email, len(trades), round(total_pnl, 2), wins)
            reports_sent += 1

    return {"status": "ok", "reports_sent": reports_sent}


@celery_app.task(name="backend.tasks.send_trade_notification", bind=True, max_retries=3)
def send_trade_notification(self, user_email: str, symbol: str, side: str, price: float,
                            qty: float, pnl_pct: float = None):
    """Notifica la ejecución de un trade (async)."""
    from backend.notifications import notify_trade
    try:
        notify_trade(user_email, symbol, side, price, qty, pnl_pct)
        return {"status": "ok"}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(name="backend.tasks.send_circuit_breaker_alert")
def send_circuit_breaker_alert(user_email: str, reason: str, loss_pct: float):
    """Notifica la activación de un circuit breaker."""
    from backend.notifications import notify_circuit_breaker
    notify_circuit_breaker(user_email, reason, loss_pct)
    return {"status": "ok"}


@celery_app.task(name="backend.tasks.backtest_symbol")
def backtest_symbol(user_id: int, symbol: str, interval: str, limit: int = 1000):
    """Ejecuta un backtest pesado en background."""
    from src.backtest.engine import BacktestEngine
    from src.data.binance_client import BinanceDataClient
    from backend.user_config import load_user_config

    cfg = load_user_config(user_id)
    client = BinanceDataClient()
    df = client.fetch_klines(symbol, interval, limit=limit)
    if df is None or df.empty:
        return {"status": "error", "detail": "sin datos"}

    engine = BacktestEngine(config=cfg)
    result = engine.run(df, symbol=symbol)
    return {"status": "ok", "symbol": symbol, "result": result}