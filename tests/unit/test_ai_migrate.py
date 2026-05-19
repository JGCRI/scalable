"""Unit tests for scalable.ai.manifest_migrate module."""

from __future__ import annotations

import json

import pytest
import yaml

from scalable.ai.manifest_migrate import MigrationResult, migrate_manifest
from scalable.manifest.parser import parse_manifest


def _make_manifest(tmp_path):
    """Create a minimal test manifest."""
    manifest_content = {
        "version": 1,
        "project": {"name": "test-project"},
        "targets": {
            "local": {"provider": "local", "max_workers": 4},
            "hpc": {"provider": "slurm", "queue": "short", "walltime": "02:00:00"},
        },
        "components": {
            "gcam": {
                "image": "ghcr.io/jgcri/scalable-gcam:7.0",
                "runtime": "apptainer",
                "cpus": 6,
                "memory": "20G",
                "tags": ["iam"],
            },
        },
        "tasks": {
            "run_gcam": {"component": "gcam", "cache": True},
        },
    }
    manifest_path = tmp_path / "scalable.yaml"
    manifest_path.write_text(yaml.dump(manifest_content))
    return manifest_path


class TestMigrateManifest:
    def test_migrate_to_kubernetes(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        result = migrate_manifest(
            manifest_path=manifest_path,
            to_provider="kubernetes",
            no_ai=True,
        )
        assert isinstance(result, MigrationResult)
        assert result.method == "heuristic"
        assert result.overlay_yaml is not None
        assert "kubernetes" in result.overlay_yaml

    def test_migrate_to_aws(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        result = migrate_manifest(
            manifest_path=manifest_path,
            to_provider="aws",
            no_ai=True,
        )
        assert "aws" in result.overlay_yaml

    def test_migrate_to_unknown_provider(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        result = migrate_manifest(
            manifest_path=manifest_path,
            to_provider="unknown_provider",
            no_ai=True,
        )
        assert result.overlay_yaml is None
        assert "No template" in result.changes_description

    def test_migrate_version_same(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        result = migrate_manifest(
            manifest_path=manifest_path,
            to_version=1,
            no_ai=True,
        )
        assert "No changes needed" in result.changes_description or "current" in result.changes_description.lower()

    def test_migrate_version_downgrade(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        result = migrate_manifest(
            manifest_path=manifest_path,
            to_version=0,
            no_ai=True,
        )
        assert "downgrade" in result.changes_description.lower() or result.warnings

    def test_migrate_optimize(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        result = migrate_manifest(
            manifest_path=manifest_path,
            goal="Optimize manifest for production",
            no_ai=True,
        )
        assert result.changes_description  # Should have some suggestions

    def test_no_manifest_raises(self):
        with pytest.raises(ValueError, match="(?i)must provide"):
            migrate_manifest(to_provider="kubernetes", no_ai=True)

    def test_nonexistent_manifest_raises(self, tmp_path):
        with pytest.raises(Exception):
            migrate_manifest(
                manifest_path=tmp_path / "nonexistent.yaml",
                to_provider="kubernetes",
                no_ai=True,
            )

    def test_render_text(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        result = migrate_manifest(
            manifest_path=manifest_path,
            to_provider="kubernetes",
            no_ai=True,
        )
        text = result.render_text()
        assert "Migration" in text
        assert "kubernetes" in text.lower()

    def test_to_dict_serializable(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        result = migrate_manifest(
            manifest_path=manifest_path,
            to_provider="kubernetes",
            no_ai=True,
        )
        d = result.to_dict()
        serialized = json.dumps(d)
        assert "overlay_yaml" in serialized

    def test_cloud_migration_warnings(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        result = migrate_manifest(
            manifest_path=manifest_path,
            to_provider="kubernetes",
            no_ai=True,
        )
        # Should warn about mount path changes
        assert any("mount" in w.lower() or "image" in w.lower() for w in result.warnings)
