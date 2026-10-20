from fastapi import APIRouter

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.post("/webhook")
async def alerts_webhook(payload: dict):
    alerts = payload.get("alerts", [])
    received = []
    for a in alerts:
        labels = a.get("labels", {})
        annotations = a.get("annotations", {})
        entry = {
            "status": a.get("status"),
            "alertname": labels.get("alertname"),
            "severity": labels.get("severity"),
            "summary": annotations.get("summary"),
            "description": annotations.get("description"),
        }
        received.append(entry)
        try:
            from backend.services.notifications import notify_risk_alert

            notify_risk_alert(
                "monitoring",
                f"[{entry['severity']}] {entry['alertname']}: {entry['summary'] or ''}",
            )
        except Exception:
            pass
    return {"received": len(alerts), "alerts": received}
