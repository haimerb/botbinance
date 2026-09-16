import hashlib
import os
import pandas as pd
import joblib
from src.config import MODEL_PATH
from src.models.trainer import add_technical_features, FEATURE_COLS


MODEL_INTEGRITY_HASH = os.getenv("MODEL_INTEGRITY_HASH", "")


class ModelIntegrityError(Exception):
    pass


class MLStrategy:
    def __init__(self, model_path: str = MODEL_PATH,
                 confidence_threshold: float = 0.55,
                 high_confidence: float = 0.7):
        self.dir_model = None
        self.vol_pipeline = None
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.high_confidence = high_confidence
        self._feature_cache = {}
        self._load_model()

    def _verify_model_integrity(self) -> bool:
        if not MODEL_INTEGRITY_HASH:
            return True
        try:
            with open(self.model_path, "rb") as f:
                content = f.read()
            actual_hash = hashlib.sha256(content).hexdigest()
            expected_hash = MODEL_INTEGRITY_HASH.split(":")[-1] if ":" in MODEL_INTEGRITY_HASH else MODEL_INTEGRITY_HASH
            if actual_hash != expected_hash:
                raise ModelIntegrityError(
                    f"Model integrity check failed: expected {expected_hash}, got {actual_hash}"
                )
            return True
        except FileNotFoundError:
            raise ModelIntegrityError(f"Model file not found: {self.model_path}")

    def _load_model(self):
        try:
            self._verify_model_integrity()
            data = joblib.load(self.model_path)
            if isinstance(data, dict):
                self.dir_model = data.get("dir_model")
                self.vol_pipeline = data.get("vol_pipeline")
            print("Modelos ML cargados.")
        except FileNotFoundError:
            print("Modelo ML no encontrado. Ejecuta train_model.py")
        except ModelIntegrityError as e:
            print(f"ERROR DE INTEGRIDAD DEL MODELO: {e}")
            self.dir_model = None
            self.vol_pipeline = None

    def _prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df_hash = hashlib.md5(pd.util.hash_pandas_object(df).values.tobytes()).hexdigest()
        if df_hash in self._feature_cache:
            return self._feature_cache[df_hash]
        result = add_technical_features(df).dropna()
        self._feature_cache[df_hash] = result
        if len(self._feature_cache) > 100:
            self._feature_cache.clear()
        return result

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
