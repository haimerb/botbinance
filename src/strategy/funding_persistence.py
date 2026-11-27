import statistics
from collections import Counter
from dataclasses import dataclass

HIGH_RATE = 0.0003
MID_RATE = 0.0001


@dataclass
class FundingPersistenceModel:
    """Estima si el siguiente funding seguirá siendo positivo.

    Modelo empírico con suavizado de Laplace: agrupa por símbolo, tramo de
    funding y longitud de la racha positiva. No predice precios.
    """

    target_rate: float = 0.00005
    min_samples: int = 20
    counts: dict = None

    def __post_init__(self):
        if self.counts is None:
            self.counts = Counter()

    @staticmethod
    def _bucket(rate):
        if rate <= 0:
            return "neg"
        if rate < MID_RATE:
            return "low"
        if rate < HIGH_RATE:
            return "mid"
        return "high"

    @staticmethod
    def _streak(history):
        streak = 0
        for rate in reversed(history):
            if rate <= 0:
                break
            streak += 1
        return min(streak, 5)

    def _features(self, history):
        if not history:
            return ("empty", 0)
        return (self._bucket(history[-1]), self._streak(history))

    def fit(self, history_by_symbol):
        for symbol, rates in history_by_symbol.items():
            values = [float(rate) for rate in rates]
            for index in range(len(values) - 1):
                features = self._features(values[:index + 1])
                outcome = values[index + 1] >= self.target_rate
                self.counts[(symbol, features, outcome)] += 1
        return self

    def predict(self, symbol, rate, history):
        features = self._features(list(history) + [float(rate)])
        yes = self.counts.get((symbol, features, True), 0)
        no = self.counts.get((symbol, features, False), 0)
        total = yes + no
        if total < self.min_samples:
            return None
        return (yes + 1) / (total + 2)

    @staticmethod
    def trailing_volatility(history, window=10):
        recent = list(history)[-window:]
        if len(recent) < 2:
            return 0.0
        return statistics.pstdev(recent)
