from paper_watch import (
    METRICAS,
    maxima_metrica,
    resumen,
    sumar_metrica,
    valor_metrica,
)


def test_valor_metrica_con_etiquetas():
    texto = """
    # HELP botbinance_funding_decisions_total Decisiones
    botbinance_funding_decisions_total{result="allowed"} 7
    botbinance_funding_errors_total 2
    """
    assert valor_metrica(texto, "botbinance_funding_decisions_total") == 7
    assert valor_metrica(texto, "botbinance_funding_errors_total") == 2
    assert valor_metrica(texto, "botbinance_funding_missing") is None


def test_agregadores_de_metricas_etiquetadas():
    texto = """
    botbinance_funding_decisions_total{result="allowed"} 2
    botbinance_funding_decisions_total{result="rejected"} 3
    botbinance_funding_errors_total 1
    botbinance_funding_liquidation_pressure{symbol="BTCUSDT"} 0.3
    botbinance_funding_liquidation_pressure{symbol="SOLUSDT"} 0.7
    """
    assert sumar_metrica(texto, "botbinance_funding_decisions_total") == 5
    assert sumar_metrica(texto, "botbinance_funding_errors_total") == 1
    assert maxima_metrica(texto, "botbinance_funding_liquidation_pressure") == 0.7
    assert sumar_metrica(texto, "botbinance_funding_missing") is None


def test_resumen_con_oportunidad_y_posicion():
    estado = {
        "status": "running",
        "cycles": 12,
        "position": {"symbol": "SOLUSDT", "is_hedged": True},
        "accounting": {"net": 0.71234},
        "gate": {"persistence_trained": True},
        "opportunities": [
            {"symbol": "BTCUSDT", "annual_net_pct": 0.12},
            {"symbol": "SOLUSDT", "annual_net_pct": 10.95},
        ],
    }
    metricas = "\n".join(f"{nombre} 1" for nombre in METRICAS)
    resultado = resumen(estado, metricas)
    assert resultado["estado"] == "running"
    assert resultado["mejor_simbolo"] == "SOLUSDT"
    assert resultado["mejor_neto_anual_pct"] == 10.95
    assert resultado["posicion"] == "SOLUSDT"
    assert resultado["cubierta"] is True
    assert resultado["pnl_neto_usd"] == 0.7123
    assert resultado["metricas_ok"] is True
    assert resultado["decisiones"] == 1


def test_resumen_sin_oportunidades():
    estado = {"status": "running", "cycles": 1, "accounting": {}, "gate": {}}
    resultado = resumen(estado, "")
    assert resultado["mejor_simbolo"] is None
    assert resultado["mejor_neto_anual_pct"] == 0
    assert resultado["posicion"] is None
    assert resultado["metricas_ok"] is False
    assert resultado["ultima_ejecucion"] is None
    assert resultado["fills_registrados"] == 0
    assert resultado["slippage_promedio_bps"] is None


def test_resumen_incluye_evidencia_de_ejecucion():
    estado = {
        "status": "running",
        "cycles": 4,
        "accounting": {"net": 0.2},
        "gate": {},
        "execution": {
            "last_execution": {"action": "open", "mode": "dry_run"},
            "fills": [
                {"slippage_bps": 0},
                {"slippage_bps": 4},
                {"slippage_bps": None},
            ],
        },
    }
    resultado = resumen(estado, "")
    assert resultado["ultima_ejecucion"] == {"action": "open", "mode": "dry_run"}
    assert resultado["fills_registrados"] == 3
    assert resultado["slippage_promedio_bps"] == 2.0
