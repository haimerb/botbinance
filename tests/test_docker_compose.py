from pathlib import Path

VARIABLES = (
    "DRY_RUN",
    "FUNDING_ENABLED",
    "FUNDING_POLL_SECONDS",
    "FUNDING_MIN_ANNUAL_PCT",
    "FUNDING_NOTIONAL_USDT",
    "FUNDING_LEVERAGE",
    "FUNDING_EXIT_IF_NEGATIVE",
    "FUNDING_SYMBOLS",
    "FUNDING_HISTORY_BASE_URL",
    "FUNDING_MIN_INTERVALS",
    "FUNDING_MAX_ZSCORE",
    "FUNDING_MAX_BASIS_PCT",
    "FUNDING_HISTORY_WINDOW",
    "FUNDING_EVENT_BLACKOUT_MINUTES",
    "FUNDING_LIQUIDATION_PRESSURE_ENABLED",
    "FUNDING_MAX_LIQUIDATION_PRESSURE",
    "FUNDING_LIQUIDATION_TARGET_RATE",
    "FUNDING_MIN_HOLD_DAYS",
    "FUNDING_MAKER_TIMEOUT_SECONDS",
    "FUNDING_MAKER_FEE",
    "FUNDING_TAKER_FEE",
    "FUNDING_USE_MAKER",
    "FUNDING_MAKER_PRICE_OFFSET",
    "FUNDING_MIN_FALLBACK_ANNUAL_PCT",
    "FUNDING_USE_PERSISTENCE",
    "FUNDING_MIN_PERSISTENCE_PROB",
    "FUNDING_PERSISTENCE_MIN_SAMPLES",
    "FUNDING_PERSISTENCE_TARGET_RATE",
)


def test_compose_pasa_variables_de_funding_al_backend():
    texto = Path("docker-compose.yml").read_text(encoding="utf-8")
    for nombre in VARIABLES:
        assert f"{nombre}: ${{{nombre}:" in texto


def test_compose_dry_run_por_defecto_es_seguro():
    texto = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "DRY_RUN: ${DRY_RUN:-true}" in texto
    assert "FUNDING_ENABLED: ${FUNDING_ENABLED:-false}" in texto
