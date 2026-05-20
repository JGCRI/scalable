"""Tests for scalable.ml.models — ML model wrappers."""

from __future__ import annotations

import pandas as pd
import pytest

from scalable.ml.models import ModelQuality, PredictionResult, ResourceModel


class TestPredictionResult:
    def test_creation(self):
        p = PredictionResult(point=100.0, lower=80.0, upper=120.0, confidence=0.9)
        assert p.point == 100.0
        assert p.lower == 80.0
        assert p.upper == 120.0

    def test_to_dict(self):
        p = PredictionResult(point=50.0)
        d = p.to_dict()
        assert d["point"] == 50.0
        assert d["confidence"] == 0.95


class TestModelQuality:
    def test_creation(self):
        q = ModelQuality(
            mae=5.0, rmse=7.0, r2=0.85, coverage=0.92,
            n_samples=100, model_type="gradient_boosting", target_name="duration"
        )
        assert q.mae == 5.0
        assert q.r2 == 0.85

    def test_to_dict(self):
        q = ModelQuality(
            mae=5.0, rmse=7.0, r2=0.85, coverage=0.92,
            n_samples=100, model_type="rf", target_name="mem"
        )
        d = q.to_dict()
        assert d["model_type"] == "rf"
        assert d["n_samples"] == 100


class TestResourceModel:
    def test_not_fitted_raises(self):
        model = ResourceModel()
        with pytest.raises(RuntimeError, match="not fitted"):
            model.predict(pd.DataFrame({"x": [1]}))

    def test_fit_empty_data(self):
        model = ResourceModel()
        X = pd.DataFrame()
        y = pd.Series(dtype=float)
        model.fit(X, y)
        assert model.is_fitted
        # Predict returns fallback
        result = model.predict(pd.DataFrame({"x": [1]}))
        assert len(result) == 1

    def test_fit_single_row(self):
        model = ResourceModel()
        X = pd.DataFrame({"feat1": [1.0]})
        y = pd.Series([100.0])
        model.fit(X, y)
        assert model.is_fitted
        result = model.predict(pd.DataFrame({"feat1": [1.0]}))
        assert len(result) == 1
        assert result[0].point == 100.0  # Median of single value

    def test_fit_few_rows_uses_percentile_fallback(self):
        model = ResourceModel()
        X = pd.DataFrame({"feat1": [1.0, 2.0, 3.0]})
        y = pd.Series([100.0, 200.0, 300.0])
        model.fit(X, y)
        assert model.is_fitted
        result = model.predict(pd.DataFrame({"feat1": [2.0]}))
        assert len(result) == 1
        # Should work regardless of sklearn availability

    def test_feature_importances_unfitted(self):
        model = ResourceModel()
        assert model.feature_importances() == {}

    def test_model_types(self):
        for model_type in ["gradient_boosting", "random_forest", "quantile_regression"]:
            model = ResourceModel(model_type=model_type)
            assert model.model_type == model_type

    def test_save_load(self, tmp_path):
        model = ResourceModel()
        X = pd.DataFrame({"feat1": [1.0, 2.0]})
        y = pd.Series([10.0, 20.0])
        model.fit(X, y)

        save_path = tmp_path / "test_model"
        model.save(save_path)
        assert (save_path / "metadata.json").exists()

        loaded = ResourceModel.load(save_path)
        assert loaded.is_fitted
        assert loaded.model_type == model.model_type
