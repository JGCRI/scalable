"""Unit tests for TelemetryStore persistence primitives."""

from __future__ import annotations

import json
from pathlib import Path

from scalable.manifest.parser import load_manifest
from scalable.planning.dryrun import build_dry_run_plan
from scalable.providers.base import DeploymentSpec
from scalable.telemetry.store import TelemetryStore


def _write_manifest(path: Path) -> None:
    path.write_text(
        """
version: 1
project:
  name: demo
targets:
  local:
    provider: local
components:
  gcam:
    cpus: 2
    memory: 8G
tasks:
  run_gcam:
    component: gcam
""".lstrip(),
        encoding="utf-8",
    )


def test_store_writes_bootstrap_and_summary(tmp_path: Path) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    _write_manifest(manifest_path)

    manifest = load_manifest(manifest_path)
    spec = DeploymentSpec.from_manifest(manifest, target_name="local")
    plan = build_dry_run_plan(spec)

    store = TelemetryStore.create(
        runs_dir=tmp_path / "runs",
        manifest=manifest,
        spec=spec,
        plan=plan,
    )

    store.record_task_submission(
        task_id="t1",
        task_name="run_gcam",
        component="gcam",
        tag="gcam",
        function_name="run_gcam",
        requested_workers=1,
    )
    store.record_task_result(
        task_id="t1",
        task_name="run_gcam",
        component="gcam",
        tag="gcam",
        function_name="run_gcam",
        requested_workers=1,
        state="succeeded",
    )
    store.record_cache_event(
        function_name="run_gcam",
        key_digest="123",
        hit=False,
        duration_s=0.1,
        task_name="run_gcam",
        component="gcam",
        tag="gcam",
    )
    store.close(status="completed")

    run_dir = store.run_dir
    assert (run_dir / "manifest.yaml").exists()
    assert (run_dir / "plan.json").exists()
    assert (run_dir / "manifest.lock").exists()
    assert (run_dir / "run.json").exists()
    assert (run_dir / "summary.json").exists()

    run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert run_payload["status"] == "completed"
    assert summary["counts"]["task_events"] >= 3

