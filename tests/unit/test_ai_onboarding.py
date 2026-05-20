"""Unit tests for scalable.ai.component_onboarding module."""

from __future__ import annotations

import pytest
import yaml

from scalable.ai.component_onboarding import OnboardingResult, onboard_component


class TestOnboardComponent:
    def test_nonexistent_directory_raises(self):
        with pytest.raises(FileNotFoundError):
            onboard_component("/nonexistent/path/xyz")

    def test_basic_python_project(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname='mymodel'")
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "data").mkdir()

        result = onboard_component(tmp_path, name="mymodel", no_ai=True)

        assert isinstance(result, OnboardingResult)
        assert result.name == "mymodel"
        assert result.method == "heuristic"
        assert "mymodel" in result.component_yaml
        assert result.scan.languages  # Should detect Python

    def test_default_name_from_directory(self, tmp_path):
        model_dir = tmp_path / "My_Model"
        model_dir.mkdir()
        (model_dir / "run.py").write_text("pass")

        result = onboard_component(model_dir, no_ai=True)
        assert result.name == "my-model"

    def test_cpp_project_higher_resources(self, tmp_path):
        (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.10)")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.cpp").write_text("int main() { return 0; }")
        (tmp_path / "exe").mkdir()

        result = onboard_component(tmp_path, name="gcam", no_ai=True)

        # Should detect C++ and suggest higher resources
        assert result.scan.estimated_cpus >= 4
        assert "compiled" in result.scan.suggested_tags

    def test_output_is_valid_yaml(self, tmp_path):
        (tmp_path / "app.py").write_text("pass")
        (tmp_path / "requirements.txt").write_text("numpy")

        result = onboard_component(tmp_path, name="test", no_ai=True)

        # The YAML portion should be parseable (after stripping comments)
        lines = result.component_yaml.split("\n")
        yaml_lines = [l for l in lines if not l.startswith("#")]
        yaml_content = "\n".join(yaml_lines)
        parsed = yaml.safe_load(yaml_content)
        assert parsed is not None
        assert "test" in parsed

    def test_dockerfile_detected(self, tmp_path):
        (tmp_path / "Dockerfile").write_text("FROM python:3.11")
        (tmp_path / "app.py").write_text("pass")

        result = onboard_component(tmp_path, name="test", no_ai=True)
        assert "Dockerfile" in result.scan.container_files

    def test_mounts_from_data_dirs(self, tmp_path):
        (tmp_path / "data").mkdir()
        (tmp_path / "output").mkdir()
        (tmp_path / "main.py").write_text("pass")

        result = onboard_component(tmp_path, name="test", no_ai=True)
        assert result.scan.suggested_mounts  # Should suggest mounting data dirs

    def test_warnings_on_low_confidence(self, tmp_path):
        # Empty directory = low confidence
        result = onboard_component(tmp_path, name="empty", no_ai=True)
        assert any("confidence" in w.lower() or "Low" in w for w in result.warnings)

    def test_to_dict_returns_component(self, tmp_path):
        (tmp_path / "app.py").write_text("pass")
        result = onboard_component(tmp_path, name="mycomp", no_ai=True)
        d = result.to_dict()
        assert isinstance(d, dict)
