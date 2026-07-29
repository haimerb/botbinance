import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import TimeSeriesSplit
from sklearn.model_selection import RandomizedSearchCV
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier, StackingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import Pipeline as ImbPipeline
import xgboost as xgb

try:
    import lightgbm as lgb
    HAS_LGBM = True
except ImportError:
    HAS_LGBM = False

try:
    from catboost import CatBoostClassifier
    HAS_CAT = True
except ImportError:
    HAS_CAT = False

from src.config import MODEL_PATH, DEFAULT_SYMBOLS, INTERVAL
from src.data.binance_client import BinanceDataClient


def add_technical_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["returns_1"] = df["close"].pct_change(1)
    df["returns_3"] = df["close"].pct_change(3)
    df["returns_5"] = df["close"].pct_change(5)

    for w in [5, 10, 20, 50]:
        df[f"sma_{w}"] = df["close"].rolling(w).mean()

    ema_12 = df["close"].ewm(span=12).mean()
    ema_26 = df["close"].ewm(span=26).mean()
    df["macd"] = ema_12 - ema_26
    macd_signal = df["macd"].ewm(span=9).mean()
    df["macd_diff"] = df["macd"] - macd_signal

    df["high_low_pct"] = (df["high"] - df["low"]) / df["close"]

    df["atr"] = df["high"] - df["low"]
    df["atr_ratio"] = df["atr"].rolling(14).mean() / df["close"]

    for w in [5, 10, 20]:
        df[f"volatility_{w}"] = df["returns_1"].rolling(w).std()

    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df["rsi"] = 100 - (100 / (1 + rs))
    df["rsi_ma"] = df["rsi"].rolling(5).mean()
    df["rsi_14_ma"] = df["rsi"].rolling(14).mean()

    low_14 = df["low"].rolling(14).min()
    high_14 = df["high"].rolling(14).max()
    df["williams_r"] = ((high_14 - df["close"]) / (high_14 - low_14 + 1e-10)) * -100

    df["adx"] = abs(df["close"].diff())
    df["adx_smoothed"] = df["adx"].rolling(14).mean()
    df["plus_dm"] = df["high"].diff().clip(lower=0)
    df["minus_dm"] = (-df["low"].diff()).clip(lower=0)
    df["plus_di"] = (df["plus_dm"].rolling(14).mean() / df["atr"].rolling(14).mean() * 100)
    df["minus_di"] = (df["minus_dm"].rolling(14).mean() / df["atr"].rolling(14).mean() * 100)
    df["adx_final"] = (abs(df["plus_di"] - df["minus_di"]) / (df["plus_di"] + df["minus_di"] + 1e-10)).rolling(14).mean() * 100

    sr_level_20 = df["close"].rolling(20).mean()
    df["close_to_sr"] = df["close"] / sr_level_20 - 1

    df["volume_sma_5"] = df["volume"].rolling(5).mean()
    df["volume_sma_20"] = df["volume"].rolling(20).mean()
    df["vol_cross"] = df["volume_sma_5"] / df["volume_sma_20"] - 1

    df["bb_mid"] = df["close"].rolling(20).mean()
    df["bb_std"] = df["close"].rolling(20).std()
    df["bb_pos"] = (df["close"] - (df["bb_mid"] - 2 * df["bb_std"])) / (4 * df["bb_std"] + 1e-10)

    vol_ma = df["volume"].rolling(10).mean()
    df["volume_ratio"] = df["volume"] / vol_ma

    for w in [5, 10, 20]:
        df[f"close_to_sma{w}"] = df["close"] / df[f"sma_{w}"] - 1

    df["max_10"] = df["high"].rolling(10).max()
    df["min_10"] = df["low"].rolling(10).min()
    df["stoch_k"] = (df["close"] - df["min_10"]) / (df["max_10"] - df["min_10"] + 1e-10)
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()

    return df


FEATURE_COLS = [
    "returns_1", "returns_3", "returns_5",
    "sma_5", "sma_10", "sma_20", "sma_50",
    "macd", "macd_diff",
    "high_low_pct",
    "volatility_5", "volatility_10", "volatility_20",
    "rsi", "rsi_ma", "rsi_14_ma",
    "williams_r",
    "adx_final", "plus_di", "minus_di",
    "bb_pos",
    "volume_ratio", "vol_cross",
    "close_to_sma5", "close_to_sma10", "close_to_sma20",
    "close_to_sr",
    "stoch_k", "stoch_d",
    "atr_ratio",
]


def prepare_training_data(df: pd.DataFrame) -> pd.DataFrame:
    df = add_technical_features(df)

    for h in [3, 6, 12]:
        df[f"ret_{h}"] = df["close"].shift(-h) / df["close"] - 1

    df["up_count"] = 0
    threshold = df["ret_6"].quantile(0.55)
    for h in [3, 6, 12]:
        df["up_count"] += (df[f"ret_{h}"] > threshold).astype(int)
    df["target"] = (df["up_count"] >= 2).astype(int)

    vol_threshold = df["volatility_5"].shift(-6).quantile(0.6)
    df["vol_target"] = (df["volatility_5"].shift(-6) > vol_threshold).astype(int)

    df = df.dropna().reset_index(drop=True)
    return df


def _build_base_estimators():
    est = [
        ("xgb", xgb.XGBClassifier(
            objective="binary:logistic", eval_metric="logloss",
            random_state=42, n_jobs=-1, max_delta_step=1,
        )),
    ]
    if HAS_LGBM:
        est.append(("lgbm", lgb.LGBMClassifier(
            objective="binary", random_state=42, n_jobs=-1, verbose=-1,
        )))
    if HAS_CAT:
        est.append(("cat", CatBoostClassifier(
            loss_function="Logloss", random_seed=42, verbose=0,
        )))
    return est


def _make_stacking() -> StackingClassifier:
    return StackingClassifier(
        estimators=_build_base_estimators(),
        final_estimator=LogisticRegression(random_state=42, C=1.0, max_iter=1000),
        cv=3,
        stack_method="predict_proba",
        n_jobs=-1,
    )


def train_direction_model(X_train, y_train, X_test, y_test):
    print("\n--- Modelo de DIRECCIÓN (Stacking Ensemble) ---")

    pipeline = ImbPipeline([
        ("smote", SMOTE(random_state=42)),
        ("scaler", StandardScaler()),
        ("stack", _make_stacking()),
    ])

    print(f"  Base learners: {[n for n, _ in _build_base_estimators()]}")
    print(f"  Meta learner: LogisticRegression")

    param_grid = {
        "stack__xgb__n_estimators": [150, 300],
        "stack__xgb__max_depth": [3, 6],
        "stack__xgb__learning_rate": [0.03, 0.07],
        "stack__final_estimator__C": [0.1, 1.0, 10.0],
    }
    if HAS_LGBM:
        param_grid["stack__lgbm__num_leaves"] = [31, 63]
        param_grid["stack__lgbm__learning_rate"] = [0.03, 0.07]
    if HAS_CAT:
        param_grid["stack__cat__depth"] = [4, 7]
        param_grid["stack__cat__learning_rate"] = [0.03, 0.07]

    tscv = TimeSeriesSplit(n_splits=3)
    search = RandomizedSearchCV(
        pipeline, param_grid, n_iter=8, cv=tscv,
        scoring="accuracy", random_state=42, n_jobs=-1, verbose=0,
    )
    search.fit(X_train, y_train)

    print("\n--- Validación Cruzada (por fold) ---")
    for i, (train_idx, val_idx) in enumerate(tscv.split(X_train)):
        fold_pipe = ImbPipeline([
            ("smote", SMOTE(random_state=42)),
            ("scaler", StandardScaler()),
            ("stack", _make_stacking()),
        ])
        fold_pipe.set_params(**search.best_params_)
        fold_pipe.fit(X_train[train_idx], y_train[train_idx])
        fold_acc = accuracy_score(y_train[val_idx], fold_pipe.predict(X_train[val_idx]))
        print(f"  Fold {i+1}: {fold_acc:.2%}")

    best = search.best_estimator_
    print(f"\nMejores params: {search.best_params_}")

    y_pred = best.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"\nTest accuracy: {acc:.2%}")
    print(classification_report(y_test, y_pred, target_names=["DOWN", "UP"]))

    cm = confusion_matrix(y_test, y_pred)
    tn, fp, fn, tp = cm.ravel()
    print(f"TN={tn} FP={fp} FN={fn} TP={tp}")
    print(f"UP recall: {tp/(tp+fn):.1%} | UP precision: {tp/(tp+fp):.1%}")

    return best


def train_volatility_model(X_train, y_train, X_test, y_test):
    print("\n--- Modelo de VOLATILIDAD ---")

    pipeline = ImbPipeline([
        ("smote", SMOTE(random_state=42)),
        ("scaler", StandardScaler()),
        ("rf", RandomForestClassifier(
            n_estimators=300, max_depth=10, min_samples_leaf=5,
            class_weight="balanced", random_state=42, n_jobs=-1,
        )),
    ])
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"RF Test: {acc:.2%}")
    print(classification_report(y_test, y_pred, target_names=["LOW", "HIGH"]))
    return pipeline


def train_model():
    print("=" * 50)
    print("  ENTRENAMIENTO ML DEFINITIVO")
    print("=" * 50)

    print("\nObteniendo datos históricos (real API)...")
    client = BinanceDataClient()
    df = client.fetch_klines(DEFAULT_SYMBOLS[0], INTERVAL, 5000, use_real_api=True)
    if df.empty:
        print("Fallback a testnet...")
        df = client.fetch_klines(DEFAULT_SYMBOLS[0], INTERVAL, 2000)
    if df.empty:
        print("Sin datos.")
        return

    print(f"Velas: {len(df)} ({df.timestamp.iloc[0].date()} -> {df.timestamp.iloc[-1].date()})")

    df = prepare_training_data(df)
    print(f"Muestras: {len(df)}")

    up = df["target"].sum()
    down = len(df) - up
    print(f"Dirección: UP={up} ({up/len(df):.1%}) DOWN={down} ({down/len(df):.1%})")

    high_vol = df["vol_target"].sum()
    low_vol = len(df) - high_vol
    print(f"Volatilidad: HIGH={high_vol} ({high_vol/len(df):.1%}) LOW={low_vol} ({low_vol/len(df):.1%})")

    X = df[FEATURE_COLS].values
    y_dir = df["target"].values
    y_vol = df["vol_target"].values

    split = int(len(X) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_dir_train, y_dir_test = y_dir[:split], y_dir[split:]
    y_vol_train, y_vol_test = y_vol[:split], y_vol[split:]

    print(f"\nTrain: {len(X_train)} | Test: {len(X_test)}")

    dir_model = train_direction_model(X_train, y_dir_train, X_test, y_dir_test)
    vol_pipeline = train_volatility_model(X_train, y_vol_train, X_test, y_vol_test)

    joblib.dump({
        "dir_model": dir_model,
        "vol_pipeline": vol_pipeline,
        "features": FEATURE_COLS,
    }, MODEL_PATH)
    print(f"\nModelos guardados en {MODEL_PATH}")


if __name__ == "__main__":
    train_model()
