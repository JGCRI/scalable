"""Unit tests for :mod:`scalable.manifest.parser` (Phase 1 WU-2).

This suite focuses on syntax/schema parsing and environment expansion only.
Cross-field semantic checks (unknown component references, provider registry
lookups, memory parseability, mount path policy) are covered in
``test_manifest_validate.py`` under WU-3.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scalable.manifest.errors import ManifestParseError, ManifestSchemaError
from scalable.manifest.parser import expand_env_vars, load_manifest, parse_manifest
from scalable.manifest.schema import SCHEMA_VERSION


def test_expand_env_vars_expands_recursive_tree() -> None:
    env = {
        "ROOT": "/data",
        "IMAGE_TAG": "7.0",
        "OMP": "6",
    }
    tree = {
        "a": "${ROOT}/inputs",
        "b": ["x", "${ROOT}/outputs", {"c": "ghcr.io/demo:${IMAGE_TAG}"}],
        "d": {"OMP_NUM_THREADS": "${OMP}"},
    }

    out = expand_env_vars(tree, env=env)

    assert out == {
        "a": "/data/inputs",
        "b": ["x", "/data/outputs", {"c": "ghcr.io/demo:7.0"}],
        "d": {"OMP_NUM_THREADS": "6"},
    }


def test_expand_env_vars_supports_default_clause() -> None:
    tree = {
        "path": "${UNSET_VAR:-/tmp/default}",
        "nested": ["${OTHER_UNSET:-fallback}"]
    }
    out = expand_env_vars(tree, env={})
    assert out == {"path": "/tmp/default", "nested": ["fallback"]}


def test_expand_env_vars_raises_when_unset_without_default() -> None:
    with pytest.raises(ManifestParseError, match="not set"):
        expand_env_vars({"path": "${MISSING}"}, env={})


def test_parse_manifest_from_mapping_success() -> None:
    manifest = {
        "version": SCHEMA_VERSION,
        "project": {"name": "ia-workflow", "local_cache": "./.scalable/cache"},
        "targets": {
            "local": {
                "provider": "local",
                "max_workers": 4,
                "containers": "none",
            }
        },
        "components": {
            "gcam": {
                "image": "ghcr.io/jgcri/scalable-gcam:7.0",
                "runtime": "apptainer",
                "cpus": 6,
                "memory": "20G",
                "mounts": {"/host/data": "/data"},
                "env": {"OMP_NUM_THREADS": "6"},
                "tags": ["iam", "climate"],
            }
        },
        "tasks": {
            "run_gcam": {
                "component": "gcam",
                "cache": True,
                "outputs": {"database": "dir"},
            }
        },
    }

    model = parse_manifest(manifest)

    assert model.version == SCHEMA_VERSION
    assert model.project.name == "ia-workflow"
    assert "local" in model.targets
    assert model.targets["local"].provider == "local"
    # target extras are provider passthrough and preserved
    assert model.targets["local"].options["max_workers"] == 4
    assert model.targets["local"].options["containers"] == "none"
    assert model.components["gcam"].cpus == 6
    assert model.tasks["run_gcam"].cache is True


def test_parse_manifest_from_yaml_string_with_env_expansion() -> None:
    yaml_text = """
version: 1
project:
  name: integrated-assessment-workflow
  default_storage: ${STORAGE_URI}
targets:
  hpc:
    provider: slurm
    queue: short
    account: GCIMS
components:
  gcam:
    image: ghcr.io/jgcri/scalable-gcam:${GCAM_TAG}
    runtime: apptainer
    cpus: 6
    memory: 20G
tasks:
  run_gcam:
    component: gcam
    cache: true
"""
    env = {
        "STORAGE_URI": "s3://my-bucket/scalable-runs/",
        "GCAM_TAG": "7.0",
    }

    model = parse_manifest(yaml_text, env=env)

    assert model.project.default_storage == "s3://my-bucket/scalable-runs/"
    assert model.components["gcam"].image == "ghcr.io/jgcri/scalable-gcam:7.0"


def test_load_manifest_from_file_sets_source_path(tmp_path: Path) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    manifest_path.write_text(
        """
version: 1
project:
  name: demo
""".lstrip(),
        encoding="utf-8",
    )

    model = load_manifest(manifest_path)

    assert model.project.name == "demo"
    assert model.source_path == str(manifest_path)


def test_parse_manifest_rejects_empty_document() -> None:
    with pytest.raises(ManifestSchemaError, match="empty"):
        parse_manifest("")


def test_parse_manifest_rejects_non_mapping_top_level() -> None:
    with pytest.raises(ManifestSchemaError, match="top level"):
        parse_manifest("- not\n- a\n- mapping\n")


def test_parse_manifest_rejects_malformed_yaml() -> None:
    with pytest.raises(ManifestParseError, match="malformed YAML"):
        parse_manifest("version: [1\n")


def test_parse_manifest_rejects_unknown_top_level_keys() -> None:
    with pytest.raises(ManifestSchemaError, match="unknown top-level"):
        parse_manifest(
            {
                "version": 1,
                "project": {"name": "demo"},
                "componentz": {},
            }
        )


def test_parse_manifest_rejects_missing_required_top_level_keys() -> None:
    with pytest.raises(ManifestSchemaError, match="missing required"):
        parse_manifest({"version": 1})


def test_parse_manifest_rejects_non_integer_version() -> None:
    with pytest.raises(ManifestSchemaError, match="must be an integer"):
        parse_manifest({"version": "1", "project": {"name": "demo"}})


def test_parse_manifest_rejects_unsupported_version() -> None:
    with pytest.raises(ManifestSchemaError, match="not supported"):
        parse_manifest({"version": 999, "project": {"name": "demo"}})


def test_parse_manifest_rejects_invalid_project_name() -> None:
    with pytest.raises(ManifestSchemaError, match=r"project\.name"):
        parse_manifest({"version": 1, "project": {"name": ""}})


def test_parse_manifest_rejects_unknown_project_key() -> None:
    with pytest.raises(ManifestSchemaError, match="unknown 'project'"):
        parse_manifest(
            {
                "version": 1,
                "project": {"name": "demo", "unknown": "x"},
            }
        )


def test_parse_manifest_rejects_target_without_provider() -> None:
    with pytest.raises(ManifestSchemaError, match=r"targets\.local\.provider"):
        parse_manifest(
            {
                "version": 1,
                "project": {"name": "demo"},
                "targets": {"local": {}},
            }
        )


def test_parse_manifest_rejects_unknown_component_key() -> None:
    with pytest.raises(ManifestSchemaError, match=r"unknown 'components\.gcam'"):
        parse_manifest(
            {
                "version": 1,
                "project": {"name": "demo"},
                "components": {
                    "gcam": {
                        "cpus": 1,
                        "weird": True,
                    }
                },
            }
        )


def test_parse_manifest_rejects_component_invalid_types() -> None:
    with pytest.raises(ManifestSchemaError, match="cpus"):
        parse_manifest(
            {
                "version": 1,
                "project": {"name": "demo"},
                "components": {"gcam": {"cpus": 0}},
            }
        )

    with pytest.raises(ManifestSchemaError, match="memory"):
        parse_manifest(
            {
                "version": 1,
                "project": {"name": "demo"},
                "components": {"gcam": {"memory": 32}},
            }
        )

    with pytest.raises(ManifestSchemaError, match="mounts"):
        parse_manifest(
            {
                "version": 1,
                "project": {"name": "demo"},
                "components": {"gcam": {"mounts": ["/a:/b"]}},
            }
        )

    with pytest.raises(ManifestSchemaError, match="env"):
        parse_manifest(
            {
                "version": 1,
                "project": {"name": "demo"},
                "components": {"gcam": {"env": ["OMP=6"]}},
            }
        )

    with pytest.raises(ManifestSchemaError, match="tags"):
        parse_manifest(
            {
                "version": 1,
                "project": {"name": "demo"},
                "components": {"gcam": {"tags": "climate"}},
            }
        )


def test_parse_manifest_rejects_unknown_task_key() -> None:
    with pytest.raises(ManifestSchemaError, match=r"unknown 'tasks\.run_gcam'"):
        parse_manifest(
            {
                "version": 1,
                "project": {"name": "demo"},
                "tasks": {
                    "run_gcam": {
                        "component": "gcam",
                        "unexpected": "x",
                    }
                },
            }
        )


def test_parse_manifest_rejects_task_invalid_types() -> None:
    with pytest.raises(ManifestSchemaError, match="component"):
        parse_manifest(
            {
                "version": 1,
                "project": {"name": "demo"},
                "tasks": {"run_gcam": {"component": 5}},
            }
        )

    with pytest.raises(ManifestSchemaError, match="cache"):
        parse_manifest(
            {
                "version": 1,
                "project": {"name": "demo"},
                "tasks": {"run_gcam": {"component": "gcam", "cache": "yes"}},
            }
        )

    with pytest.raises(ManifestSchemaError, match="outputs"):
        parse_manifest(
            {
                "version": 1,
                "project": {"name": "demo"},
                "tasks": {"run_gcam": {"component": "gcam", "outputs": ["dir"]}},
            }
        )
