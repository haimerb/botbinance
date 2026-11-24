import functools

import numpy as np
import pytest

from src.models import trainer


# xgboost usa `early_stopping_rounds`, lightgbm `early_stopping_round`
EARLY_STOPPING_KEYS = ("early_stopping_rounds", "early_stopping_round")


def test_base_estimators_have_no_early_stopping():
    # StackingClassifier no pasa eval_set a los base learners; con early stopping
    # activo el fit falla ("Must have at least 1 validation dataset").
    for name, est in trainer._build_base_estimators():
        params = est.get_params()
        for key in EARLY_STOPPING_KEYS:
            assert params.get(key) is None, f"{name}.{key} debe ser None"


def test_stacking_fits_synthetic_data():
    rng = np.random.default_rng(0)
    X = rng.standard_normal((60, 5))
    y = (X[:, 0] + rng.standard_normal(60) * 0.1 > 0).astype(int)

    stack = trainer._make_stacking()
    stack.fit(X, y)
    preds = stack.predict(X)
    assert len(preds) == 60


@pytest.fixture
def cheap_catboost(monkeypatch):
    """CatBoost con sus 1000 iteraciones por defecto domina el tiempo del test;
    con 50 se ejercita la misma ruta de entrenamiento en ~2 s."""
    if trainer.HAS_CAT:
        monkeypatch.setattr(
            trainer, "CatBoostClassifier",
            functools.partial(trainer.CatBoostClassifier, iterations=50),
        )


def test_direction_model_search_runs_end_to_end(cheap_catboost):
    """Regresión del bug completo: la búsqueda con TimeSeriesSplit + SMOTE
    debe entrenar y dejar el xgb ajustado sin early stopping."""
    rng = np.random.default_rng(1)
    X = rng.standard_normal((300, 6))
    y = (X[:, 0] + X[:, 1] + rng.standard_normal(300) * 0.1 > 0).astype(int)

    model, metrics = trainer.train_direction_model(
        X[:240], y[:240], X[240:], y[240:], n_iter=1
    )

    fitted_xgb = model.named_steps["stack"].named_estimators_["xgb"]
    assert fitted_xgb.get_params()["early_stopping_rounds"] is None
    assert metrics["test_samples"] == 60
    assert 0.0 <= metrics["dir_accuracy"] <= 1.0
