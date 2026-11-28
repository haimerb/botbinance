import json

import paper_forward_report as report


def test_leer_snapshot_usa_estado_y_metricas(monkeypatch):
    vistas = []

    def peticion_falsa(url, token=None):
        vistas.append((url, token))
        if url.endswith("/api/funding/status"):
            return json.dumps({
                "status": "running",
                "cycles": 3,
                "accounting": {"net": 1.25, "max_drawdown_usd": 0.2},
            })
        return "botbinance_funding_running 1\n"

    monkeypatch.setattr(report, "peticion", peticion_falsa)
    snapshot = report.leer_snapshot("http://localhost:8000/", "jwt")

    assert snapshot["estado"] == "running"
    assert snapshot["ciclos"] == 3
    assert snapshot["pnl_neto_usd"] == 1.25
    assert snapshot["drawdown_usd"] == 0.2
    assert vistas[0][1] == "jwt"


def test_append_y_resumen_acumula_snapshots(tmp_path):
    archivo = tmp_path / "paper.jsonl"
    primer = {
        "ts": 100.0,
        "ciclos": 1,
        "pnl_neto_usd": -0.1,
        "drawdown_usd": 0.1,
        "drawdown_pct": 0.1,
        "decisiones": 1,
        "errores": 0,
        "fills_registrados": 2,
        "slippage_promedio_bps": 1.0,
        "metricas_ok": False,
    }
    segundo = {
        "ts": 200.0,
        "ciclos": 4,
        "pnl_neto_usd": 0.5,
        "drawdown_usd": 0.4,
        "drawdown_pct": 0.4,
        "decisiones": 3,
        "errores": 1,
        "fills_registrados": 6,
        "slippage_promedio_bps": 2.0,
        "metricas_ok": True,
    }
    report.append_snapshot(archivo, primer)
    report.append_snapshot(archivo, segundo)

    resultado = report.resumir_snapshots(archivo)
    assert resultado["snapshots"] == 2
    assert resultado["primer_ts"] == 100.0
    assert resultado["ultimo_ts"] == 200.0
    assert resultado["ciclos"] == 4
    assert resultado["pnl_neto_usd"] == 0.5
    assert resultado["drawdown_usd"] == 0.4
    assert resultado["errores"] == 1
    assert resultado["slippage_promedio_bps"] == 1.5
    assert resultado["metricas_ok"] is True


def test_resumen_sin_archivo_devuelve_cero(tmp_path):
    assert report.resumir_snapshots(tmp_path / "sin-datos.jsonl") == {"snapshots": 0}
