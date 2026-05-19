"""Tests for ModelConfig deprecation behavior (Phase 1 WU-7)."""

from __future__ import annotations

import warnings
from pathlib import Path

from scalable.utilities import ModelConfig, model_config_adapter_context


def _write_minimal_dockerfile(path: Path) -> None:
    path.write_text(
        """
FROM ubuntu:22.04 AS gcam
""".lstrip(),
        encoding="utf-8",
    )


def test_modelconfig_direct_init_emits_deprecation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    _write_minimal_dockerfile(tmp_path / "Dockerfile")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        ModelConfig(path=str(tmp_path / "config_dict.yaml"), path_overwrite=True)

    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecations) >= 1
    assert "ModelConfig Dockerfile discovery is deprecated" in str(deprecations[0].message)


def test_modelconfig_inside_adapter_context_suppresses_deprecation(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_minimal_dockerfile(tmp_path / "Dockerfile")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        with model_config_adapter_context():
            config = ModelConfig(path=str(tmp_path / "config_dict.yaml"), path_overwrite=True)

    assert isinstance(config, ModelConfig)
    deprecations = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert deprecations == []
