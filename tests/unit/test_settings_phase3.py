"""Unit tests for Phase 3 Settings extensions."""

from __future__ import annotations

import os

import pytest

from scalable.common import Settings


class TestSettingsPhase3:
    def test_cache_remote_uri_default_none(self):
        # Unset env var
        env = os.environ.copy()
        env.pop("SCALABLE_CACHE_REMOTE", None)
        with pytest.MonkeyPatch.context() as m:
            m.delenv("SCALABLE_CACHE_REMOTE", raising=False)
            s = Settings()
            assert s.cache_remote_uri is None

    def test_cache_remote_uri_from_env(self):
        with pytest.MonkeyPatch.context() as m:
            m.setenv("SCALABLE_CACHE_REMOTE", "s3://my-bucket/cache/")
            s = Settings()
            assert s.cache_remote_uri == "s3://my-bucket/cache/"

    def test_default_storage_default_none(self):
        with pytest.MonkeyPatch.context() as m:
            m.delenv("SCALABLE_DEFAULT_STORAGE", raising=False)
            s = Settings()
            assert s.default_storage is None

    def test_default_storage_from_env(self):
        with pytest.MonkeyPatch.context() as m:
            m.setenv("SCALABLE_DEFAULT_STORAGE", "gs://bucket/artifacts/")
            s = Settings()
            assert s.default_storage == "gs://bucket/artifacts/"

    def test_runs_dir_remote_default_none(self):
        with pytest.MonkeyPatch.context() as m:
            m.delenv("SCALABLE_RUNS_DIR_REMOTE", raising=False)
            s = Settings()
            assert s.runs_dir_remote is None

    def test_runs_dir_remote_from_env(self):
        with pytest.MonkeyPatch.context() as m:
            m.setenv("SCALABLE_RUNS_DIR_REMOTE", "s3://bucket/runs/")
            s = Settings()
            assert s.runs_dir_remote == "s3://bucket/runs/"
