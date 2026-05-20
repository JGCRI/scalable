"""Unit tests for deterministic ResourceAdvisor recommendations."""

from __future__ import annotations

import json
from pathlib import Path

from scalable.advising import ResourceAdvisor


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8")


def _seed_run(run_dir: Path, *, duration_s: float, cpus: int, memory: str, workers: int) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_dir.name,
                "target_name": "local",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    _append_jsonl(
        run_dir / "tasks.jsonl",
        [
            {
                "task_id": "t1",
                "task_name": "run_gcam",
                "component": "gcam",
                "state": "succeeded",
                "duration_s": duration_s,
            }
        ],
    )
    _append_jsonl(
        run_dir / "resources.jsonl",
        [
            {
                "entity_type": "task",
                "entity_id": "t1",
                "requested_workers": workers,
                "requested_cpus": cpus,
                "requested_memory": memory,
                "requested_walltime": "00:30:00",
            }
        ],
    )


def test_resource_advisor_returns_history_based_recommendation(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    _seed_run(
        runs / "run-20260519T120000Z-demo-aaaa1111",
        duration_s=120.0,
        cpus=4,
        memory="8G",
        workers=1,
    )
    _seed_run(
        runs / "run-20260519T130000Z-demo-bbbb2222",
        duration_s=300.0,
        cpus=6,
        memory="16G",
        workers=2,
    )

    advisor = ResourceAdvisor.from_history(runs)
    recommendation = advisor.recommend(task="run_gcam", target="local", confidence=0.95)

    assert recommendation.task == "run_gcam"
    assert recommendation.target == "local"
    assert "gcam" in recommendation.workers
    assert recommendation.workers["gcam"] >= 1
    assert recommendation.resources["gcam"]["cpus"] >= 1
    assert recommendation.evidence["records"] >= 2


def test_resource_advisor_handles_missing_history(tmp_path: Path) -> None:
    advisor = ResourceAdvisor.from_history(tmp_path / "runs")
    recommendation = advisor.recommend(task="missing_task", target="local")

    assert recommendation.workers == {"missing_task": 1}
    assert recommendation.resources["missing_task"]["cpus"] == 1
    assert recommendation.evidence["records"] == 0

