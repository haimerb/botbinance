import joblib


def test_trained_model_has_all_keys_and_real_metrics():
    data = joblib.load("src/models/trained_model.pkl")

    assert "dir_model" in data
    assert "vol_pipeline" in data
    assert "features" in data
    assert "metrics" in data
    assert "symbols" in data
    assert "interval" in data

    assert len(data["features"]) == 30
    assert "stack" in data["dir_model"].named_steps

    metrics = data["metrics"]
    for key in ("dir_accuracy", "up_recall", "up_precision", "vol_accuracy", "trained_at"):
        assert metrics.get(key) is not None, f"métrica {key} es nula"


def test_ml_strategy_reads_real_metrics():
    from src.strategy.ml_strategy import MLStrategy

    strategy = MLStrategy()
    metrics = strategy.get_metrics()

    assert metrics["model_loaded"] is True
    assert metrics["model_accuracy"] is not None
    assert metrics["up_recall"] is not None
    assert metrics["trained_at"] is not None
