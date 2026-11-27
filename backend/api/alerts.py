from fastapi import APIRouter, Depends, Query

from backend.core.config import alert_store
from backend.core.deps import get_current_user

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.post("/webhook")
async def alerts_webhook(payload: dict):
    received = alert_store.add(payload)
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


@router.get("/recent")
def recent_alerts(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100),
):
    return {"alerts": alert_store.list(limit)}
