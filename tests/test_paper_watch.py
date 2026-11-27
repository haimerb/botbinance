from paper_watch import METRICAS, resumen, valor_metrica


def test_valor_metrica_con_etiquetas():
    texto = """
    # HELP botbinance_funding_decisions_total Decisiones
    botbinance_funding_decisions_total{result="allowed"} 7
    botbinance_funding_errors_total 2
    """
    assert valor_metrica(texto, "botbinance_funding_decisions_total") == 7
    assert valor_metrica(texto, "botbinance_funding_errors_total") == 2
    assert valor_metrica(texto, "botbinance_funding_missing") is None


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
