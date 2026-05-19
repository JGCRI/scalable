"""Unit tests for telemetry collectors and report rendering."""

from __future__ import annotations

import json
from pathlib import Path

from scalable.telemetry.collectors import (
    latest_run_dir,
    read_jsonl,
    render_text_report,
    resolve_run_dir,
    summarize_run,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    payload = "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n"
    path.write_text(payload, encoding="utf-8")


def _seed_run(run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_dir.name,
                "project_name": "demo",
                "target_name": "local",
                "provider_name": "local",
                "status": "completed",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_jsonl(
        run_dir / "tasks.jsonl",
        [
            {
                "task_id": "t1",
                "task_name": "run_gcam",
                "component": "gcam",
                "state": "succeeded",
                "duration_s": 3.5,
            },
            {
                "task_id": "t2",
                "task_name": "run_gcam",
                "component": "gcam",
                "state": "failed",
                "duration_s": 1.0,
            },
        ],
    )
    _write_jsonl(
        run_dir / "resources.jsonl",
        [
            {
                "entity_type": "task",
                "entity_id": "t1",
                "requested_cpus": 4,
            },
            {
                "entity_type": "task",
                "entity_id": "t2",
                "requested_cpus": 6,
            },
        ],
    )
    _write_jsonl(
        run_dir / "cache.jsonl",
        [
            {"hit": False},
            {"hit": True},
        ],
    )
    _write_jsonl(
        run_dir / "failures.jsonl",
        [
            {"failure_class": "RuntimeError"},
            {"failure_class": "RuntimeError"},
        ],
    )


def test_read_jsonl_missing_returns_empty(tmp_path: Path) -> None:
    assert read_jsonl(tmp_path / "missing.jsonl") == []


def test_summarize_run_and_render_text(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-20260519T120000Z-demo-aaaa1111"
    _seed_run(run_dir)

    summary = summarize_run(run_dir)
    text = render_text_report(summary)

    assert summary["counts"]["tasks_succeeded"] == 1
    assert summary["counts"]["tasks_failed"] == 1
    assert summary["cache"]["hits"] == 1
    assert summary["cache"]["misses"] == 1
    assert "run_id:" in text
    assert "tasks:" in text


def test_resolve_run_dir_latest_and_id(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    run1 = runs / "run-20260519T120000Z-demo-aaaa1111"
    run2 = runs / "run-20260519T130000Z-demo-bbbb2222"
    _seed_run(run1)
    _seed_run(run2)

    assert latest_run_dir(runs) == run2
    assert resolve_run_dir(runs_dir=runs, latest=True) == run2
    assert resolve_run_dir(runs_dir=runs, run_id=run1.name) == run1

