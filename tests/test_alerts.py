import asyncio

from backend.api.alerts import alerts_webhook
from backend.core.config import alert_store
from backend.services.alert_store import AlertStore


def test_alert_store_devuelve_mas_recientes_primero():
    store = AlertStore(maxlen=2)
    store.add(
        {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "Primera", "severity": "warning"},
                    "annotations": {"summary": "resumen uno"},
                }
            ]
        }
    )
    store.add(
        {
            "alerts": [
                {
                    "status": "resolved",
                    "labels": {"alertname": "Segunda", "severity": "critical"},
                    "annotations": {"summary": "resumen dos"},
                }
            ]
        }
    )
    items = store.list()
    assert [item["alertname"] for item in items] == ["Segunda", "Primera"]
    assert items[0]["description"] is None
    assert items[0]["severity"] == "critical"


def test_webhook_almacena_y_devuelve_alertas():
    alert_store.clear()
    payload = {
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": "FundingRunnerErrores", "severity": "critical"},
                "annotations": {"summary": "Errores del runner", "description": "Muchos errores"},
                "fingerprint": "abc123",
                "startsAt": "2026-11-27T00:00:00Z",
            }
        ]
    }
    result = asyncio.run(alerts_webhook(payload))
    assert result["received"] == 1
    assert result["alerts"][0]["alertname"] == "FundingRunnerErrores"
    stored = alert_store.list(1)[0]
    assert stored["fingerprint"] == "abc123"
    assert stored["received_at"] > 0
