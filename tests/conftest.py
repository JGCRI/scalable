"""Pytest configuration shared across the :mod:`scalable` test suite.

This file intentionally stays small. Heavyweight HPC/Slurm/Docker fixtures
are kept out of unit tests so the suite can run on a developer laptop or a
plain CI runner without external dependencies.
"""

from __future__ import annotations

import os
import sys

import pytest


@pytest.fixture(autouse=True)
def _isolate_scalable_env(tmp_path, monkeypatch):
    """Ensure each test runs with isolated cache/log/work directories.

    The package historically reads ``./cache``, ``./logs``, ``./containers``
    and similar paths from the current working directory. To prevent tests
    from polluting each other (or the developer's repo), we ``chdir`` into a
    fresh temporary directory and clear the environment overrides.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SCALABLE_CACHE_DIR", raising=False)
    monkeypatch.delenv("SCALABLE_SEED", raising=False)
    monkeypatch.delenv("SCALABLE_LOG_LEVEL", raising=False)
    monkeypatch.delenv("COMM_PORT", raising=False)
    yield


@pytest.fixture
def fresh_settings(monkeypatch):
    """Yield a freshly-initialized :class:`scalable.common.Settings` instance.

    Mutates the singleton in :mod:`scalable.common` for the duration of the
    test and restores it afterwards.
    """
    from scalable import common

    original = common.settings
    new = common.Settings()
    monkeypatch.setattr(common, "settings", new)
    try:
        yield new
    finally:
        monkeypatch.setattr(common, "settings", original)


# Make the ``scalable`` package importable without an editable install in
# environments where pytest is invoked from the repo root.
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
