import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request

from backend.core.config import ALERT_WEBHOOK_TOKEN, alert_store, limiter
from backend.core.deps import get_current_user
from backend.schemas import AlertmanagerWebhookPayload

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def verify_webhook_token(authorization: str | None) -> None:
    if not ALERT_WEBHOOK_TOKEN or not authorization:
        raise HTTPException(status_code=401, detail="Token de webhook requerido")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(token, ALERT_WEBHOOK_TOKEN):
        raise HTTPException(status_code=401, detail="Token de webhook inválido")


def process_webhook(payload: AlertmanagerWebhookPayload) -> dict:
    received = alert_store.add(payload.model_dump())
    for entry in received:
        try:
            from backend.services.notifications import notify_risk_alert

            notify_risk_alert(
                "monitoring",
                f"[{entry['severity']}] {entry['alertname']}: {entry['summary'] or ''}",
            )
        except Exception:
            pass
    return {"received": len(received), "alerts": received}


@router.post("/webhook")
@limiter.limit("30/minute")
async def alerts_webhook(
    request: Request,
    payload: AlertmanagerWebhookPayload,
    authorization: str | None = Header(None),
):
    verify_webhook_token(authorization)
    return process_webhook(payload)


@router.get("/recent")
def recent_alerts(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
):
    return {"alerts": alert_store.list(limit)}
