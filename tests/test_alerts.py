import pytest
from fastapi import HTTPException

import backend.api.alerts as alerts_api
from backend.core.config import alert_store
from backend.schemas import AlertmanagerWebhookPayload
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
    result = alerts_api.process_webhook(AlertmanagerWebhookPayload(**payload))
    assert result["received"] == 1
    assert result["alerts"][0]["alertname"] == "FundingRunnerErrores"
    stored = alert_store.list(1)[0]
    assert stored["fingerprint"] == "abc123"
    assert stored["received_at"] > 0


def test_webhook_rechaza_token_ausente(monkeypatch):
    monkeypatch.setattr(alerts_api, "ALERT_WEBHOOK_TOKEN", "token-de-prueba")
    with pytest.raises(HTTPException) as exc:
        alerts_api.verify_webhook_token(None)
    assert exc.value.status_code == 401


def test_webhook_rechaza_token_invalido(monkeypatch):
    monkeypatch.setattr(alerts_api, "ALERT_WEBHOOK_TOKEN", "token-de-prueba")
    with pytest.raises(HTTPException) as exc:
        alerts_api.verify_webhook_token("Bearer incorrecto")
    assert exc.value.status_code == 401


def test_webhook_acepta_token_valido(monkeypatch):
    monkeypatch.setattr(alerts_api, "ALERT_WEBHOOK_TOKEN", "token-de-prueba")
    alerts_api.verify_webhook_token("Bearer token-de-prueba")


def test_webhook_valida_payload_con_valores_por_defecto():
    payload = AlertmanagerWebhookPayload(
        alerts=[{"status": "firing", "labels": {"alertname": "Prueba"}}]
    )
    alert = payload.alerts[0]
    assert alert.labels.severity == "info"
    assert alert.annotations.summary is None
