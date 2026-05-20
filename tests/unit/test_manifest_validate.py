"""Unit tests for :mod:`scalable.manifest.validate` (Phase 1 WU-3)."""

from __future__ import annotations

from scalable.manifest.parser import parse_manifest
from scalable.manifest.validate import validate_manifest


def _base_manifest() -> dict:
    return {
        "version": 1,
        "project": {"name": "demo"},
        "targets": {
            "local": {
                "provider": "local",
                "max_workers": 4,
            }
        },
        "components": {
            "gcam": {
                "cpus": 2,
                "memory": "8G",
                "mounts": {
                    "/host/data": "/data",
                },
            }
        },
        "tasks": {
            "run_gcam": {
                "component": "gcam",
                "cache": True,
            }
        },
    }


def test_validate_manifest_ok_for_valid_manifest() -> None:
    model = parse_manifest(_base_manifest())

    report = validate_manifest(model)

    assert report.ok is True
    assert report.errors == []
    assert report.warnings == []


def test_validate_manifest_warns_when_no_targets_or_tasks() -> None:
    manifest = {
        "version": 1,
        "project": {"name": "demo"},
        "targets": {},
        "components": {},
        "tasks": {},
    }
    model = parse_manifest(manifest)

    report = validate_manifest(model)

    assert report.ok is True
    assert len(report.warnings) == 2
    warning_paths = {w.path for w in report.warnings}
    assert "targets" in warning_paths
    assert "tasks" in warning_paths


def test_validate_manifest_errors_for_unknown_provider() -> None:
    manifest = _base_manifest()
    manifest["targets"]["local"]["provider"] = "kubernetes"
    model = parse_manifest(manifest)

    report = validate_manifest(model, known_providers={"local", "slurm"})

    assert report.ok is False
    assert len(report.errors) == 1
    issue = report.errors[0]
    assert issue.path == "targets.local.provider"
    assert issue.code == "E_UNKNOWN_PROVIDER"
    assert "unknown provider" in issue.message


def test_validate_manifest_accepts_custom_known_provider_set() -> None:
    manifest = _base_manifest()
    manifest["targets"]["local"]["provider"] = "kubernetes"
    model = parse_manifest(manifest)

    report = validate_manifest(model, known_providers={"local", "slurm", "kubernetes"})

    assert report.ok is True
    assert report.errors == []


def test_validate_manifest_errors_for_unknown_task_component() -> None:
    manifest = _base_manifest()
    manifest["tasks"]["run_gcam"]["component"] = "missing_component"
    model = parse_manifest(manifest)

    report = validate_manifest(model)

    assert report.ok is False
    assert len(report.errors) == 1
    issue = report.errors[0]
    assert issue.path == "tasks.run_gcam.component"
    assert issue.code == "E_UNKNOWN_COMPONENT"
    assert "unknown component" in issue.message


def test_validate_manifest_errors_for_unparseable_memory() -> None:
    manifest = _base_manifest()
    manifest["components"]["gcam"]["memory"] = "not-a-memory"
    model = parse_manifest(manifest)

    report = validate_manifest(model)

    assert report.ok is False
    assert len(report.errors) == 1
    issue = report.errors[0]
    assert issue.path == "components.gcam.memory"
    assert issue.code == "E_BAD_MEMORY"
    assert "not parseable" in issue.message


def test_validate_manifest_errors_for_nonpositive_memory() -> None:
    manifest = _base_manifest()
    manifest["components"]["gcam"]["memory"] = "0B"
    model = parse_manifest(manifest)

    report = validate_manifest(model)

    assert report.ok is False
    assert len(report.errors) == 1
    issue = report.errors[0]
    assert issue.path == "components.gcam.memory"
    assert issue.code == "E_NONPOSITIVE_MEMORY"
    assert "greater than zero" in issue.message


def test_validate_manifest_errors_for_relative_host_mount_path() -> None:
    manifest = _base_manifest()
    manifest["components"]["gcam"]["mounts"] = {
        "relative/host/path": "/data",
    }
    model = parse_manifest(manifest)

    report = validate_manifest(model)

    assert report.ok is False
    assert len(report.errors) == 1
    issue = report.errors[0]
    assert issue.path == "components.gcam.mounts['relative/host/path']"
    assert issue.code == "E_RELATIVE_HOST_MOUNT"


def test_validate_manifest_errors_for_relative_container_mount_path() -> None:
    manifest = _base_manifest()
    manifest["components"]["gcam"]["mounts"] = {
        "/host/data": "relative/container/path",
    }
    model = parse_manifest(manifest)

    report = validate_manifest(model)

    assert report.ok is False
    assert len(report.errors) == 1
    issue = report.errors[0]
    assert issue.path == "components.gcam.mounts['/host/data']"
    assert issue.code == "E_RELATIVE_CONTAINER_MOUNT"


def test_validate_manifest_collects_multiple_errors() -> None:
    manifest = _base_manifest()
    manifest["targets"]["local"]["provider"] = "mystery"
    manifest["components"]["gcam"]["memory"] = "bad"
    manifest["components"]["gcam"]["mounts"] = {
        "relative_host": "relative_container",
    }
    manifest["tasks"]["run_gcam"]["component"] = "missing"
    model = parse_manifest(manifest)

    report = validate_manifest(model)

    assert report.ok is False
    assert len(report.errors) == 5
    codes = {issue.code for issue in report.errors}
    assert "E_UNKNOWN_PROVIDER" in codes
    assert "E_BAD_MEMORY" in codes
    assert "E_RELATIVE_HOST_MOUNT" in codes
    assert "E_RELATIVE_CONTAINER_MOUNT" in codes
    assert "E_UNKNOWN_COMPONENT" in codes

