"""Integration coverage for Phase 2 session telemetry with LocalProvider."""

from __future__ import annotations

import json
from pathlib import Path

from scalable.caching import cacheable
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


@cacheable
def _cached_increment(value: int) -> int:
    return value + 1


def test_session_writes_run_telemetry_and_summary(tmp_path: Path) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    _write_manifest(manifest_path)

    session = ScalableSession.from_yaml(manifest_path, target="local")
    client = session.start()
    try:
        assert client.submit(_cached_increment, 41, tag="gcam").result(timeout=10) == 42
        assert client.submit(_cached_increment, 41, tag="gcam").result(timeout=10) == 42
    finally:
        session.close()

    runs_root = tmp_path / ".scalable" / "runs"
    run_dirs = sorted(p for p in runs_root.iterdir() if p.is_dir())
    assert len(run_dirs) == 1

    run_dir = run_dirs[0]
    assert (run_dir / "manifest.yaml").exists()
    assert (run_dir / "plan.json").exists()
    assert (run_dir / "manifest.lock").exists()
    assert (run_dir / "run.json").exists()
    assert (run_dir / "tasks.jsonl").exists()
    assert (run_dir / "summary.json").exists()

    run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert run_payload["status"] == "completed"

    summary_payload = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary_payload["counts"]["task_events"] >= 2

