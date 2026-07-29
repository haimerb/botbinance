import pandas as pd
import joblib
from src.config import MODEL_PATH
from src.models.trainer import add_technical_features, FEATURE_COLS


class MLStrategy:
    def __init__(self, model_path: str = MODEL_PATH,
                 confidence_threshold: float = 0.55,
                 high_confidence: float = 0.7):
        self.dir_model = None
        self.vol_pipeline = None
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.high_confidence = high_confidence
        self._load_model()

    def _load_model(self):
        try:
            data = joblib.load(self.model_path)
            if isinstance(data, dict):
                self.dir_model = data.get("dir_model")
                self.vol_pipeline = data.get("vol_pipeline")
            print("Modelos ML cargados.")
        except FileNotFoundError:
            print("Modelo ML no encontrado. Ejecuta train_model.py")

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = add_technical_features(df)
        return df.dropna()

    def generate_signal(self, df: pd.DataFrame) -> str:
        if self.dir_model is None:
            return "HOLD"

        features = self._prepare_features(df)
        if features.empty:
            return "HOLD"

        latest = features.iloc[[-1]]
        missing = [c for c in FEATURE_COLS if c not in latest.columns]
        if missing:
            return "HOLD"

        X = latest[FEATURE_COLS].values

        pred = self.dir_model.predict(X)[0]
        proba = self.dir_model.predict_proba(X)[0]

        confidence = max(proba)

        if confidence < self.confidence_threshold:
            return "HOLD"

        if self.vol_pipeline is not None:
            vol_pred = self.vol_pipeline.predict(X)[0]
            vol_label = "HIGH" if vol_pred == 1 else "LOW"
            if confidence < self.high_confidence and vol_label == "LOW":
                return "HOLD"

        return "BUY" if pred == 1 else "SELL"
