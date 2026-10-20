import numpy as np


class PortfolioManager:
    """Asigna capital entre múltiples símbolos según el modo configurado.

    Modos:
      - equal:        peso igual para todos los símbolos
      - volatility:   mayor peso a menor volatilidad
      - confidence:   mayor peso a mayor confianza del modelo ML
      - inverse_vol:  peso inversamente proporcional a la volatilidad
    """

    def __init__(self, mode: str = "equal"):
        self.mode = mode

    def compute_weights(self, symbols: list, volatilities: dict = None,
                        confidences: dict = None) -> dict:
        if not symbols:
            return {}

        volatilities = volatilities or {}
        confidences = confidences or {}

        if self.mode == "volatility":
            weights = self._volatility_weights(symbols, volatilities, inverse=False)
        elif self.mode == "inverse_vol":
            weights = self._volatility_weights(symbols, volatilities, inverse=True)
        elif self.mode == "confidence":
            weights = self._confidence_weights(symbols, confidences)
        else:
            weights = {s: 1.0 / len(symbols) for s in symbols}

        return self._normalize(weights)

    def _volatility_weights(self, symbols, volatilities, inverse=True):
        weights = {}
        for s in symbols:
            vol = volatilities.get(s, 0.02)
            vol = max(vol, 1e-6)
            weights[s] = (1.0 / vol) if inverse else vol
        total = sum(weights.values())
        if total <= 0:
            return {s: 1.0 / len(symbols) for s in symbols}
        return {s: w / total for s, w in weights.items()}

    def _confidence_weights(self, symbols, confidences):
        weights = {}
        for s in symbols:
            conf = confidences.get(s, 0.5)
            weights[s] = max(conf, 0.01)
        return weights

    def _normalize(self, weights):
        total = sum(weights.values())
        if total <= 0:
            n = len(weights) or 1
            return {s: 1.0 / n for s in weights}
        return {s: round(w / total, 4) for s, w in weights.items()}

    @staticmethod
    def compute_volatility(prices: list) -> float:
        """Volatilidad (desv. estándar) de una serie de precios."""
        if not prices or len(prices) < 2:
            return 0.02
        arr = np.array(prices, dtype=float)
        arr = arr[arr > 0]
        if len(arr) < 2:
            return 0.02
        returns = np.diff(arr) / arr[:-1]
        vol = float(np.std(returns))
        return max(vol, 1e-6)

    def allocate_capital(self, total_capital: float, symbols: list,
                         volatilities: dict = None, confidences: dict = None,
                         max_per_symbol_pct: float = 0.5) -> dict:
        """Devuelve el capital asignado (en USD) por símbolo, respetando un tope."""
        weights = self.compute_weights(symbols, volatilities, confidences)
        alloc = {}
        for s, w in weights.items():
            capped = min(w, max_per_symbol_pct)
            alloc[s] = round(total_capital * capped, 2)
        return alloc


def compute_kelly_fraction(win_rate: float, avg_win: float, avg_loss: float,
                           fraction: float = 0.5) -> float:
    """Fracción de Kelly (con factor de seguridad) para sizing.

    win_rate: 0..1
    avg_win / avg_loss: valores absolutos positivos
    fraction: 0.5 -> half-Kelly
    """
    if avg_loss <= 0 or win_rate <= 0:
        return 0.0
    b = avg_win / avg_loss
    p = win_rate
    q = 1 - p
    kelly = (b * p - q) / b
    return max(0.0, min(kelly * fraction, 0.25))