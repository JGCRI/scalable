"""Unit tests for scalable.ai.heuristics module."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from scalable.ai.heuristics import (
    DirectoryScanResult,
    FailureClassification,
    classify_failure,
    detect_language,
    estimate_resources,
    find_run_commands,
    scan_model_directory,
)


class TestScanModelDirectory:
    def test_scan_empty_directory(self, tmp_path):
        result = scan_model_directory(tmp_path)
        assert result.path == str(tmp_path)
        assert result.languages == []
        assert result.confidence == "low"

    def test_scan_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            scan_model_directory("/nonexistent/path/xyz")

    def test_scan_python_project(self, tmp_path):
        # Create a Python project structure
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'")
        (tmp_path / "main.py").write_text("print('hello')")
        (tmp_path / "requirements.txt").write_text("numpy\npandas")
        (tmp_path / "data").mkdir()
        (tmp_path / "README.md").write_text("# Test")

        result = scan_model_directory(tmp_path)
        assert "python" in result.languages
        assert "pyproject.toml" in result.build_systems
        assert result.has_readme is True
        assert "data" in result.data_directories
        assert result.estimated_cpus >= 1
        assert result.confidence in ("medium", "high")

    def test_scan_cpp_project(self, tmp_path):
        (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.10)")
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.cpp").write_text("int main() {}")
        (tmp_path / "exe").mkdir()

        result = scan_model_directory(tmp_path)
        assert "c++" in result.languages
        assert result.estimated_cpus >= 4
        assert "20G" == result.estimated_memory
        assert "compiled" in result.suggested_tags

    def test_scan_with_dockerfile(self, tmp_path):
        (tmp_path / "Dockerfile").write_text("FROM ubuntu:22.04")
        (tmp_path / "app.py").write_text("import sys")

        result = scan_model_directory(tmp_path)
        assert "Dockerfile" in result.container_files
        assert result.suggested_runtime in ("docker", "apptainer")

    def test_scan_with_config_files(self, tmp_path):
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "settings.xml").write_text("<settings/>")

        result = scan_model_directory(tmp_path)
        assert "config.yaml" in result.config_files
        assert "settings.xml" in result.config_files

    def test_scan_detects_tests(self, tmp_path):
        (tmp_path / "tests").mkdir()
        result = scan_model_directory(tmp_path)
        assert result.has_tests is True


class TestDetectLanguage:
    def test_empty_directory(self, tmp_path):
        langs = detect_language(tmp_path)
        assert langs == []

    def test_python_files(self, tmp_path):
        (tmp_path / "module.py").write_text("x = 1")
        (tmp_path / "test.py").write_text("y = 2")
        langs = detect_language(tmp_path)
        assert "python" in langs

    def test_mixed_languages(self, tmp_path):
        (tmp_path / "main.cpp").write_text("int main() {}")
        (tmp_path / "helper.py").write_text("x = 1")
        langs = detect_language(tmp_path)
        assert len(langs) >= 2


class TestEstimateResources:
    def test_cpp_resources(self):
        result = estimate_resources(["c++"])
        assert result["cpus"] == 6
        assert result["memory"] == "20G"

    def test_python_resources(self):
        result = estimate_resources(["python"])
        assert result["cpus"] == 2
        assert result["memory"] == "8G"

    def test_unknown_language(self):
        result = estimate_resources(["unknown"])
        assert result["cpus"] == 1
        assert result["memory"] == "4G"


class TestFindRunCommands:
    def test_no_commands(self, tmp_path):
        commands = find_run_commands(tmp_path)
        assert commands == []

    def test_makefile_targets(self, tmp_path):
        (tmp_path / "Makefile").write_text("run:\n\t./app\n\nbuild:\n\tgcc main.c")
        commands = find_run_commands(tmp_path)
        assert "make run" in commands

    def test_shell_scripts(self, tmp_path):
        (tmp_path / "run_model.sh").write_text("#!/bin/bash\necho hello")
        commands = find_run_commands(tmp_path)
        assert "./run_model.sh" in commands

    def test_python_entry(self, tmp_path):
        (tmp_path / "main.py").write_text("print('hello')")
        commands = find_run_commands(tmp_path)
        assert "python main.py" in commands


class TestClassifyFailure:
    def test_oom_detection(self):
        result = classify_failure(
            message="Process killed with signal 9 (SIGKILL) - out of memory"
        )
        assert result.failure_class == "oom"
        assert result.confidence in ("medium", "high")
        assert len(result.suggested_fixes) > 0

    def test_walltime_detection(self):
        result = classify_failure(
            failure_class="timeout",
            message="JOB CANCELLED DUE TO TIME LIMIT"
        )
        assert result.failure_class == "walltime"

    def test_mount_missing_detection(self):
        result = classify_failure(
            message="FileNotFoundError: /gcam-core/exe/configuration.xml"
        )
        assert result.failure_class == "mount_missing"

    def test_import_error_detection(self):
        result = classify_failure(
            message="ModuleNotFoundError: No module named 'scipy'"
        )
        assert result.failure_class == "import_error"

    def test_connection_error_detection(self):
        result = classify_failure(
            message="Worker failed to connect to scheduler"
        )
        assert result.failure_class == "connection"

    def test_credential_error_detection(self):
        result = classify_failure(
            message="Access denied: credential expired for S3 bucket"
        )
        assert result.failure_class == "credential"

    def test_model_runtime_detection(self):
        result = classify_failure(
            message="Segmentation fault (core dumped)"
        )
        assert result.failure_class == "model_runtime"

    def test_unknown_classification(self):
        result = classify_failure(
            message="Something unexpected happened"
        )
        assert result.failure_class == "unknown"
        assert len(result.suggested_fixes) > 0

    def test_with_resource_context(self):
        result = classify_failure(
            message="out of memory",
            resource_events=[
                {"requested_cpus": 4, "requested_memory": "8G"}
            ],
        )
        assert result.failure_class == "oom"
        assert any("8G" in ev for ev in result.evidence)
