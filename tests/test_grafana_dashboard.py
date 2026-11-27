import json
from pathlib import Path

DASHBOARD = Path("monitoring/grafana/dashboards/botbinance-trading.json")


def test_dashboard_includes_funding_panels():
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    titles = {panel["title"] for panel in dashboard["panels"]}
    assert {
        "Funding Runner / Persistencia",
        "Funding P&L Neto (USD)",
        "Funding Gate",
        "Posición de Funding",
        "Presión de Liquidaciones por Símbolo",
    } <= titles
    expressions = [
        target["expr"]
        for panel in dashboard["panels"]
        for target in panel.get("targets", [])
    ]
    assert any("botbinance_funding_running" in expr for expr in expressions)
    assert any("botbinance_funding_liquidation_pressure" in expr for expr in expressions)
