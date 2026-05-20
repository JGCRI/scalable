"""Unit tests for scalable.ai.workflow_compose module."""

from __future__ import annotations

import ast

import pytest

from scalable.ai.workflow_compose import ComposeResult, compose_workflow


class TestComposeWorkflow:
    def test_empty_description_raises(self):
        with pytest.raises(ValueError, match="empty"):
            compose_workflow("", no_ai=True)

    def test_whitespace_description_raises(self):
        with pytest.raises(ValueError, match="empty"):
            compose_workflow("   ", no_ai=True)

    def test_known_model_detection_gcam(self):
        result = compose_workflow(
            "Run GCAM reference scenario",
            no_ai=True,
        )
        assert isinstance(result, ComposeResult)
        assert "gcam" in result.detected_models
        assert result.method == "heuristic"

    def test_known_model_detection_stitches(self):
        result = compose_workflow(
            "Run Stitches for daily climate downscaling",
            no_ai=True,
        )
        assert "stitches" in result.detected_models

    def test_multi_model_workflow(self):
        result = compose_workflow(
            "Run GCAM reference and mitigation scenarios, then run Stitches for climate",
            no_ai=True,
        )
        assert "gcam" in result.detected_models
        assert "stitches" in result.detected_models

    def test_generated_workflow_is_valid_python(self):
        result = compose_workflow(
            "Run GCAM scenario",
            no_ai=True,
        )
        # Should parse as valid Python
        ast.parse(result.workflow_py)

    def test_components_yaml_parseable(self):
        import yaml

        result = compose_workflow(
            "Run GCAM and Stitches",
            no_ai=True,
        )
        parsed = yaml.safe_load(result.components_yaml)
        assert parsed is not None
        # Should have component entries
        assert isinstance(parsed, dict)

    def test_readme_generated(self):
        result = compose_workflow(
            "Run Hector simple climate model",
            no_ai=True,
        )
        assert "hector" in result.detected_models
        assert "Hector" in result.readme

    def test_unknown_model_generic_template(self):
        result = compose_workflow(
            "Run my custom model on input data",
            no_ai=True,
        )
        assert result.detected_models == []
        assert "template" in result.warnings[0].lower() or "generic" in result.warnings[0].lower()

    def test_write_to_directory(self, tmp_path):
        result = compose_workflow(
            "Run GCAM scenario",
            output_dir=tmp_path,
            no_ai=True,
        )
        assert (tmp_path / "workflow.py").exists()
        assert (tmp_path / "components.yaml").exists()
        assert (tmp_path / "README.generated.md").exists()

    def test_to_dict_serializable(self):
        import json

        result = compose_workflow("Run GCAM", no_ai=True)
        d = result.to_dict()
        serialized = json.dumps(d)
        assert "workflow.py" in serialized
        assert "detected_models" in serialized

    def test_all_known_models_detectable(self):
        models = ["gcam", "stitches", "demeter", "tethys", "xanthos", "hector"]
        for model in models:
            result = compose_workflow(f"Run {model}", no_ai=True)
            assert model in result.detected_models, f"Failed to detect {model}"
