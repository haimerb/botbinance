import os
import logging
import requests

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

TIMEOUT = 10


def _enabled() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID) or bool(DISCORD_WEBHOOK_URL)


def _send_telegram(message: str) -> bool:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=TIMEOUT,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.warning("Telegram notification failed: %s", e)
        return False


def _send_discord(message: str) -> bool:
    if not DISCORD_WEBHOOK_URL:
        return False
    try:
        resp = requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=TIMEOUT)
        return resp.status_code in (200, 204)
    except Exception as e:
        logger.warning("Discord notification failed: %s", e)
        return False


def send_notification(message: str) -> bool:
    """Envía una notificación por todos los canales configurados."""
    if not _enabled():
        logger.debug("Notifications disabled (no channels configured)")
        return False
    tg = _send_telegram(message)
    dc = _send_discord(message)
    return tg or dc


def _pnl_emoji(pnl_pct) -> str:
    if pnl_pct is None:
        return ""
    return "🟢" if pnl_pct >= 0 else "🔴"


def notify_trade(user_email: str, symbol: str, side: str, price: float, qty: float, pnl_pct=None):
    icon = "🟢" if side == "BUY" else "🔴"
    lines = [
        f"{icon} <b>Trade ejecutado</b>",
        f"Símbolo: <code>{symbol}</code>",
        f"Lado: <b>{side}</b>",
        f"Precio: {price}",
        f"Cantidad: {qty}",
    ]
    if pnl_pct is not None:
        lines.append(f"P&L: {_pnl_emoji(pnl_pct)} {pnl_pct}%")
    send_notification("\n".join(lines))


def notify_circuit_breaker(user_email: str, reason: str, loss_pct: float):
    msg = (
        f"⛔ <b>CIRCUIT BREAKER ACTIVADO</b>\n"
        f"Usuario: {user_email}\n"
        f"Motivo: {reason}\n"
        f"Pérdida: {loss_pct}%\n"
        f"El bot se ha detenido automáticamente."
    )
    send_notification(msg)


def notify_risk_alert(user_email: str, message: str):
    send_notification(f"⚠️ <b>Alerta de riesgo</b>\nUsuario: {user_email}\n{message}")


def notify_security_alert(event_type: str, detail: str, ip_address: str = None):
    lines = [
        f"🔒 <b>Alerta de seguridad</b>",
        f"Evento: <code>{event_type}</code>",
        f"Detalle: {detail}",
    ]
    if ip_address:
        lines.append(f"IP: {ip_address}")
    send_notification("\n".join(lines))


def notify_bot_error(user_email: str, error: str):
    send_notification(f"❌ <b>Error del bot</b>\nUsuario: {user_email}\n{error[:500]}")


def notify_daily_report(user_email: str, total_trades: int, total_pnl: float, wins: int):
    msg = (
        f"📊 <b>Reporte diario</b>\n"
        f"Usuario: {user_email}\n"
        f"Trades: {total_trades}\n"
        f"Ganadores: {wins}\n"
        f"P&L total: {_pnl_emoji(total_pnl)} {total_pnl}%"
    )
    send_notification(msg)