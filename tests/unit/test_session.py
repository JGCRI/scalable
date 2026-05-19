"""Unit tests for :class:`scalable.session.session.ScalableSession`."""

from __future__ import annotations

from pathlib import Path

import pytest

from scalable.session.session import ScalableSession


def _write_manifest(path: Path) -> None:
    path.write_text(
        """
version: 1
project:
  name: demo
targets:
  local:
    provider: local
    max_workers: 1
    threads_per_worker: 1
    processes: false
    containers: none
  hpc:
    provider: slurm
    comm_port: 50051
components:
  gcam:
    cpus: 1
    memory: 1G
tasks:
  run_gcam:
    component: gcam
""".lstrip(),
        encoding="utf-8",
    )


def _identity(x: int) -> int:
    return x


def test_from_yaml_explicit_target(tmp_path: Path) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    _write_manifest(manifest_path)

    session = ScalableSession.from_yaml(manifest_path, target="local")

    assert session.target_name == "local"
    assert session.spec.provider_name == "local"


def test_from_yaml_auto_prefers_local_when_not_in_slurm(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    monkeypatch.delenv("SLURM_CLUSTER_NAME", raising=False)
    manifest_path = tmp_path / "scalable.yaml"
    _write_manifest(manifest_path)

    session = ScalableSession.from_yaml(manifest_path, target="auto")

    assert session.target_name == "local"


def test_from_yaml_auto_prefers_slurm_when_in_slurm_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SLURM_JOB_ID", "12345")
    manifest_path = tmp_path / "scalable.yaml"
    _write_manifest(manifest_path)

    session = ScalableSession.from_yaml(manifest_path, target="auto")

    assert session.target_name == "hpc"


def test_validate_ok_for_local_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    monkeypatch.delenv("SLURM_CLUSTER_NAME", raising=False)
    manifest_path = tmp_path / "scalable.yaml"
    _write_manifest(manifest_path)
    session = ScalableSession.from_yaml(manifest_path, target="local")

    report = session.validate()

    assert report.ok is True


def test_plan_raises_not_implemented_for_objective_policy(tmp_path: Path) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    _write_manifest(manifest_path)
    session = ScalableSession.from_yaml(manifest_path, target="local")

    with pytest.raises(NotImplementedError):
        session.plan(objective="minimize cost")

    with pytest.raises(NotImplementedError):
        session.plan(policy="safe")


def test_plan_returns_dry_run_plan(tmp_path: Path) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    _write_manifest(manifest_path)
    session = ScalableSession.from_yaml(manifest_path, target="local")

    plan = session.plan(dry_run=True)

    assert plan.target_name == "local"
    assert plan.provider_name == "local"
    assert plan.scale_plan.workers_by_tag == {"gcam": 1}


def test_start_and_close_local_session(tmp_path: Path) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    _write_manifest(manifest_path)
    session = ScalableSession.from_yaml(manifest_path, target="local")

    client = session.start()
    future = client.submit(_identity, 7, tag="gcam")
    assert future.result(timeout=10) == 7

    session.close()


def test_start_with_target_mismatch_plan_raises(tmp_path: Path) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    _write_manifest(manifest_path)
    session_local = ScalableSession.from_yaml(manifest_path, target="local")
    session_hpc = ScalableSession.from_yaml(manifest_path, target="hpc")
    hpc_plan = session_hpc.plan(dry_run=True)

    with pytest.raises(ValueError, match="does not match session target"):
        session_local.start(hpc_plan)


def test_context_manager_starts_and_closes(tmp_path: Path) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    _write_manifest(manifest_path)
    session = ScalableSession.from_yaml(manifest_path, target="local")

    with session as client:
        result = client.submit(_identity, 11, tag="gcam").result(timeout=10)
        assert result == 11

