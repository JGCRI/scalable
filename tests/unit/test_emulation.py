"""Tests for scalable.emulation — decorator, registry, dispatch, uncertainty, active learning."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scalable.emulation.active_learning import ActiveLearner
from scalable.emulation.decorator import (
    EmulationSpec,
    emulatable,
    get_emulation_spec,
    get_original_function,
    list_emulatable_functions,
)
from scalable.emulation.dispatch import EmulatorDispatch, EmulatorDispatchResult
from scalable.emulation.registry import EmulatorInfo, EmulatorRegistry
from scalable.emulation.surrogate import (
    EmulatorMetadata,
    EmulatorPrediction,
    GradientBoostingEmulator,
    RandomForestEmulator,
)
from scalable.emulation.uncertainty import (
    CalibrationResult,
    calibrate_emulator,
    compute_confidence_from_uncertainty,
    is_in_domain,
)

# ─── Decorator tests ───


class TestEmulatable:
    def test_basic_decoration(self):
        @emulatable(
            tag="gcam",
            inputs=["carbon_price", "population"],
            outputs=["emissions"],
            confidence_threshold=0.9,
        )
        def run_gcam(params):
            return {"emissions": 100}

        spec = get_emulation_spec(run_gcam)
        assert spec is not None
        assert spec.tag == "gcam"
        assert spec.inputs == ["carbon_price", "population"]
        assert spec.outputs == ["emissions"]
        assert spec.confidence_threshold == 0.9

    def test_direct_call_runs_original(self):
        @emulatable(tag="test", inputs=["x"], outputs=["y"])
        def compute(x):
            return x * 2

        assert compute(5) == 10

    def test_get_original_function(self):
        @emulatable(tag="test", inputs=["x"], outputs=["y"])
        def compute(x):
            return x * 2

        original = get_original_function(compute)
        assert original(3) == 6

    def test_invalid_uncertainty(self):
        with pytest.raises(ValueError, match="uncertainty"):

            @emulatable(tag="t", inputs=[], outputs=[], uncertainty="invalid")
            def f():
                pass

    def test_invalid_fallback(self):
        with pytest.raises(ValueError, match="fallback"):

            @emulatable(tag="t", inputs=[], outputs=[], fallback="invalid")
            def f():
                pass

    def test_invalid_confidence(self):
        with pytest.raises(ValueError, match="confidence_threshold"):

            @emulatable(tag="t", inputs=[], outputs=[], confidence_threshold=2.0)
            def f():
                pass

    def test_list_emulatable_functions(self):
        registry = list_emulatable_functions()
        assert isinstance(registry, dict)


# ─── Surrogate model tests ───


class TestSurrogateModels:
    def _make_metadata(self):
        return EmulatorMetadata(
            name="test_emulator",
            version="1",
            training_runs=["run-1"],
            training_samples=100,
            validation_score=0.95,
            domain_bounds={"x": (0.0, 10.0)},
            created_at="2026-01-01T00:00:00Z",
            model_type="gradient_boosting",
            input_names=["x", "y"],
            output_names=["z"],
        )

    def test_gradient_boosting_emulator_no_model(self):
        meta = self._make_metadata()
        emu = GradientBoostingEmulator(metadata=meta)
        pred = emu.predict({"x": 5, "y": 3})
        assert pred.confidence == 0.0
        assert pred.is_emulated

    def test_random_forest_emulator_no_model(self):
        meta = self._make_metadata()
        emu = RandomForestEmulator(metadata=meta)
        pred = emu.predict({"x": 5, "y": 3})
        assert pred.confidence == 0.0

    def test_emulator_prediction_dataclass(self):
        pred = EmulatorPrediction(
            outputs={"z": 42.0},
            confidence=0.95,
            uncertainty_bounds={"z": (38.0, 46.0)},
        )
        assert pred.outputs["z"] == 42.0
        assert pred.is_emulated
        d = pred.to_dict()
        assert d["confidence"] == 0.95

    def test_emulator_metadata_to_dict(self):
        meta = self._make_metadata()
        d = meta.to_dict()
        assert d["name"] == "test_emulator"
        assert d["model_type"] == "gradient_boosting"


# ─── Registry tests ───


class _MockEmulator:
    """Mock emulator for testing registry without sklearn."""

    def __init__(self, name="mock", version="1"):
        self._metadata = EmulatorMetadata(
            name=name,
            version=version,
            training_runs=["run-1"],
            training_samples=50,
            validation_score=0.9,
            domain_bounds={"x": (0.0, 100.0)},
            created_at="2026-01-01T00:00:00Z",
            model_type="mock",
            input_names=["x"],
            output_names=["y"],
        )

    @property
    def metadata(self) -> EmulatorMetadata:
        return self._metadata

    def predict(self, inputs):
        return EmulatorPrediction(
            outputs={"y": float(inputs.get("x", 0)) * 2},
            confidence=0.95,
            uncertainty_bounds={"y": (0.0, 200.0)},
        )

    def uncertainty(self, inputs):
        return 0.05


class TestEmulatorRegistry:
    def test_register_and_get(self, tmp_path):
        registry = EmulatorRegistry(tmp_path / "emulators")
        emu = _MockEmulator("test", "1")
        version = registry.register("test", emu)
        assert version == "1"

        retrieved = registry.get("test")
        assert retrieved is emu

    def test_auto_version_increment(self, tmp_path):
        registry = EmulatorRegistry(tmp_path / "emulators")
        emu1 = _MockEmulator("test", "1")
        emu2 = _MockEmulator("test", "2")
        registry.register("test", emu1, version="1")
        version = registry.register("test", emu2)
        assert version == "2"

    def test_get_latest(self, tmp_path):
        registry = EmulatorRegistry(tmp_path / "emulators")
        emu1 = _MockEmulator("test", "1")
        emu2 = _MockEmulator("test", "2")
        registry.register("test", emu1, version="1")
        registry.register("test", emu2, version="2")
        retrieved = registry.get("test")
        assert retrieved is emu2

    def test_get_specific_version(self, tmp_path):
        registry = EmulatorRegistry(tmp_path / "emulators")
        emu1 = _MockEmulator("test", "1")
        emu2 = _MockEmulator("test", "2")
        registry.register("test", emu1, version="1")
        registry.register("test", emu2, version="2")
        retrieved = registry.get("test", version="1")
        assert retrieved is emu1

    def test_get_not_found(self, tmp_path):
        registry = EmulatorRegistry(tmp_path / "emulators")
        with pytest.raises(KeyError, match="not found"):
            registry.get("nonexistent")

    def test_list_emulators(self, tmp_path):
        registry = EmulatorRegistry(tmp_path / "emulators")
        registry.register("emu1", _MockEmulator("emu1", "1"))
        registry.register("emu2", _MockEmulator("emu2", "1"))
        listing = registry.list()
        assert len(listing) == 2
        names = {e.name for e in listing}
        assert "emu1" in names
        assert "emu2" in names

    def test_validate_domain_in_bounds(self, tmp_path):
        registry = EmulatorRegistry(tmp_path / "emulators")
        registry.register("test", _MockEmulator())
        assert registry.validate_domain("test", {"x": 50.0})

    def test_validate_domain_out_of_bounds(self, tmp_path):
        registry = EmulatorRegistry(tmp_path / "emulators")
        registry.register("test", _MockEmulator())
        assert not registry.validate_domain("test", {"x": 200.0})

    def test_remove(self, tmp_path):
        registry = EmulatorRegistry(tmp_path / "emulators")
        registry.register("test", _MockEmulator())
        registry.remove("test")
        with pytest.raises(KeyError):
            registry.get("test")


# ─── Dispatch tests ───


class TestEmulatorDispatch:
    def test_dispatch_with_emulator(self, tmp_path):
        registry = EmulatorRegistry(tmp_path / "emulators")
        registry.register("run_model", _MockEmulator("run_model", "1"))

        @emulatable(
            tag="test",
            inputs=["x"],
            outputs=["y"],
            confidence_threshold=0.9,
        )
        def run_model(x=0):
            return {"y": x * 3}

        dispatch = EmulatorDispatch(registry)
        result = dispatch.execute(run_model, emulator_name="run_model", x=50)
        assert result.source == "emulator"
        assert result.confidence == 0.95

    def test_dispatch_fallback_low_confidence(self, tmp_path):
        """When emulator confidence is below threshold, use full model."""

        class LowConfEmulator(_MockEmulator):
            def predict(self, inputs):
                return EmulatorPrediction(
                    outputs={"y": 0}, confidence=0.5, uncertainty_bounds={"y": (0, 100)}
                )

        registry = EmulatorRegistry(tmp_path / "emulators")
        registry.register("run_model", LowConfEmulator())

        @emulatable(
            tag="test",
            inputs=["x"],
            outputs=["y"],
            confidence_threshold=0.9,
        )
        def run_model(x=0):
            return {"y": x * 3}

        dispatch = EmulatorDispatch(registry)
        result = dispatch.execute(run_model, emulator_name="run_model", x=5)
        assert result.source == "full_model"
        assert "low_confidence" in result.fallback_reason

    def test_dispatch_no_spec(self, tmp_path):
        registry = EmulatorRegistry(tmp_path / "emulators")
        dispatch = EmulatorDispatch(registry)

        def plain_func(x):
            return x + 1

        result = dispatch.execute(plain_func, 5)
        assert result.source == "full_model"
        assert result.result == 6

    def test_dispatch_force_full_model(self, tmp_path):
        registry = EmulatorRegistry(tmp_path / "emulators")
        registry.register("run_model", _MockEmulator("run_model", "1"))

        @emulatable(tag="test", inputs=["x"], outputs=["y"])
        def run_model(x=0):
            return {"y": x * 3}

        dispatch = EmulatorDispatch(registry)
        result = dispatch.execute(run_model, emulator_name="run_model", force_full_model=True, x=5)
        assert result.source == "full_model"

    def test_dispatch_outside_domain(self, tmp_path):
        registry = EmulatorRegistry(tmp_path / "emulators")
        registry.register("run_model", _MockEmulator("run_model", "1"))

        @emulatable(
            tag="test",
            inputs=["x"],
            outputs=["y"],
            domain={"x": (0, 100)},
        )
        def run_model(x=0):
            return {"y": x * 3}

        dispatch = EmulatorDispatch(registry)
        result = dispatch.execute(run_model, emulator_name="run_model", x=200)
        assert result.source == "full_model"
        assert "outside_domain" in result.fallback_reason

    def test_dispatch_log(self, tmp_path):
        registry = EmulatorRegistry(tmp_path / "emulators")
        dispatch = EmulatorDispatch(registry, record_provenance=True)

        def f():
            return 1

        dispatch.execute(f)
        assert len(dispatch.dispatch_log) == 1


# ─── Uncertainty tests ───


class TestUncertainty:
    def test_calibrate_emulator_perfect(self):
        predictions = [
            {"outputs": {"y": 10}, "uncertainty_bounds": {"y": [5, 15]}},
            {"outputs": {"y": 20}, "uncertainty_bounds": {"y": [15, 25]}},
            {"outputs": {"y": 30}, "uncertainty_bounds": {"y": [25, 35]}},
        ]
        actuals = [{"y": 10}, {"y": 20}, {"y": 30}]
        result = calibrate_emulator(predictions, actuals, output_name="y")
        assert result.coverage_95 == 1.0
        assert result.is_calibrated

    def test_calibrate_emulator_poor(self):
        predictions = [
            {"outputs": {"y": 10}, "uncertainty_bounds": {"y": [9, 11]}},
            {"outputs": {"y": 20}, "uncertainty_bounds": {"y": [19, 21]}},
        ]
        actuals = [{"y": 50}, {"y": 100}]  # Way outside bounds
        result = calibrate_emulator(predictions, actuals, output_name="y")
        assert result.coverage_95 == 0.0
        assert not result.is_calibrated

    def test_calibrate_empty(self):
        result = calibrate_emulator([], [], output_name="y")
        assert result.n_samples == 0
        assert not result.is_calibrated

    def test_compute_confidence(self):
        assert compute_confidence_from_uncertainty(0.0) == 1.0
        assert compute_confidence_from_uncertainty(1.0) == 0.0
        assert 0.0 < compute_confidence_from_uncertainty(0.5) < 1.0

    def test_is_in_domain(self):
        domain = {"x": (0.0, 10.0), "y": (-5.0, 5.0)}
        assert is_in_domain({"x": 5.0, "y": 0.0}, domain)
        assert not is_in_domain({"x": 15.0, "y": 0.0}, domain)
        assert is_in_domain({"z": 999.0}, domain)  # Unknown keys are fine


# ─── Active learning tests ───


class TestActiveLearner:
    def test_suggest_random(self):
        learner = ActiveLearner(
            emulator=_MockEmulator(),
            acquisition="random",
            random_state=42,
        )
        candidates = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
        selected = learner.suggest(candidates, n_suggestions=2)
        assert len(selected) == 2

    def test_suggest_uncertainty(self):
        learner = ActiveLearner(
            emulator=_MockEmulator(),
            acquisition="uncertainty",
        )
        candidates = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
        selected = learner.suggest(candidates, n_suggestions=2)
        assert len(selected) == 2

    def test_suggest_expected_improvement(self):
        learner = ActiveLearner(
            emulator=_MockEmulator(),
            acquisition="expected_improvement",
        )
        candidates = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
        selected = learner.suggest(candidates, n_suggestions=2)
        assert len(selected) == 2

    def test_update_observations(self):
        learner = ActiveLearner(emulator=_MockEmulator(), acquisition="random")
        assert learner.n_observations == 0
        learner.update(pd.DataFrame({"x": [1, 2, 3]}))
        assert learner.n_observations == 3

    def test_empty_candidates(self):
        learner = ActiveLearner(emulator=_MockEmulator(), acquisition="random")
        selected = learner.suggest(pd.DataFrame(), n_suggestions=5)
        assert len(selected) == 0

    def test_invalid_acquisition(self):
        with pytest.raises(ValueError, match="acquisition"):
            ActiveLearner(emulator=_MockEmulator(), acquisition="invalid")

    def test_reset(self):
        learner = ActiveLearner(emulator=_MockEmulator(), acquisition="random")
        learner.update(pd.DataFrame({"x": [1, 2]}))
        learner.reset()
        assert learner.n_observations == 0
