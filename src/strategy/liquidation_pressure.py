import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class LiquidationPressure:
    """Riesgo de liquidaciones en cadena estimado sin datos externos.

    Es un proxy: combina crowding de funding, dislocación de basis y
    volatilidad del funding. No usa posiciones de terceros ni APIs privadas.
    """

    score: float
    source: str = "funding_basis_proxy"


def estimate_liquidation_pressure(*, zscore, basis_pct, history,
                                  max_zscore, max_basis_pct,
                                  target_rate=0.00005) -> LiquidationPressure:
    z_component = min(abs(zscore or 0) / max_zscore, 1.0) if max_zscore > 0 else 0.0
    basis_component = (
        min(abs(basis_pct or 0) / max_basis_pct, 1.0)
        if max_basis_pct > 0 else 0.0
    )
    dispersion = statistics.pstdev(list(history)) if len(history) >= 2 else 0.0
    dispersion_component = (
        min(dispersion / target_rate, 1.0) if target_rate > 0 else 0.0
    )
    score = (
        0.6 * z_component
        + 0.3 * basis_component
        + 0.1 * dispersion_component
    )
    return LiquidationPressure(round(min(score, 1.0), 4))
