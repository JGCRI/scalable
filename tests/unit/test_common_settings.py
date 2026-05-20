"""Tests for :mod:`scalable.common` settings and logger setup."""

from __future__ import annotations

import importlib
import logging

import pytest


def test_logger_has_null_handler():
    from scalable import common

    assert any(isinstance(h, logging.NullHandler) for h in common.logger.handlers), (
        "library logger must have a NullHandler attached so it does not emit "
        "by default"
    )


def test_settings_defaults():
    from scalable import common

    s = common.Settings()
    assert s.cache_dir == "./cache"
    assert s.seed == common.DEFAULT_SEED
    assert s.manifest_path == "./scalable.yaml"
    assert s.target is None
    assert s.runs_dir == "./.scalable/runs"
    assert s.telemetry_enabled is True
    assert s.telemetry_parquet is False


def test_settings_env_overrides(monkeypatch):
    monkeypatch.setenv("SCALABLE_CACHE_DIR", "/tmp/scalable-test-cache")
    monkeypatch.setenv("SCALABLE_SEED", "42")
    monkeypatch.setenv("SCALABLE_MANIFEST", "/tmp/scalable.yaml")
    monkeypatch.setenv("SCALABLE_TARGET", "local")
    monkeypatch.setenv("SCALABLE_RUNS_DIR", "/tmp/scalable-runs")
    monkeypatch.setenv("SCALABLE_TELEMETRY", "0")
    monkeypatch.setenv("SCALABLE_TELEMETRY_PARQUET", "1")

    # Reload to pick up env vars in field defaults.
    from scalable import common as common_mod

    s = common_mod.Settings()
    assert s.cache_dir == "/tmp/scalable-test-cache"
    assert s.seed == 42
    assert s.manifest_path == "/tmp/scalable.yaml"
    assert s.target == "local"
    assert s.runs_dir == "/tmp/scalable-runs"
    assert s.telemetry_enabled is False
    assert s.telemetry_parquet is True


def test_legacy_module_aliases_match_singleton():
    from scalable import common

    # The module-level ``cachedir`` and ``SEED`` are populated at import time
    # from the singleton. After mutating the singleton, the dynamic
    # ``__getattr__`` path should reflect the new value.
    common.settings.cache_dir = "/var/cache/scalable"
    common.settings.seed = 99

    # ``__getattr__`` only fires for missing names; force re-lookup by
    # deleting the cached module attributes if present.
    for name in ("cachedir", "SEED"):
        if hasattr(common, name):
            delattr(common, name)

    assert common.cachedir == "/var/cache/scalable"
    assert common.SEED == 99


def test_log_level_env_attaches_stream_handler(monkeypatch):
    """When ``SCALABLE_LOG_LEVEL`` is set, a stream handler is attached."""
    monkeypatch.setenv("SCALABLE_LOG_LEVEL", "DEBUG")
    # Force re-import so module-level code re-runs.
    import scalable.common as common_mod

    importlib.reload(common_mod)
    try:
        stream_handlers = [
            h for h in common_mod.logger.handlers if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.NullHandler)
        ]
        assert stream_handlers, "expected a StreamHandler attached when env var set"
        assert common_mod.logger.level == logging.DEBUG
    finally:
        # Detach the stream handler we just added so other tests aren't noisy.
        for h in list(common_mod.logger.handlers):
            if isinstance(h, logging.StreamHandler) and not isinstance(
                h, logging.NullHandler
            ):
                common_mod.logger.removeHandler(h)
        common_mod.logger.setLevel(logging.NOTSET)


def test_unknown_attribute_raises():
    from scalable import common

    with pytest.raises(AttributeError):
        _ = common.this_attribute_does_not_exist
