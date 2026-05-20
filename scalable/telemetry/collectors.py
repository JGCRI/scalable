"""Telemetry run loading and summary aggregation helpers."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read a newline-delimited JSON file. Missing files return an empty list."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def iter_run_dirs(runs_dir: str | Path) -> list[Path]:
    """Return existing run directories in lexicographic order."""
    root = Path(runs_dir)
    if not root.exists():
        return []
    return sorted([p for p in root.iterdir() if p.is_dir() and p.name.startswith("run-")])


def latest_run_dir(runs_dir: str | Path) -> Path:
    """Return the most recent run directory by lexicographic order."""
    runs = iter_run_dirs(runs_dir)
    if not runs:
        raise FileNotFoundError(f"no run directories found in {Path(runs_dir)!s}")
    return runs[-1]


def resolve_run_dir(
    *,
    runs_dir: str | Path,
    run_id: str | None = None,
    latest: bool = False,
) -> Path:
    """Resolve a run directory from explicit id or latest selection."""
    root = Path(runs_dir)
    if run_id is not None:
        candidate = root / run_id
        if not candidate.exists() or not candidate.is_dir():
            raise FileNotFoundError(f"run id {run_id!r} does not exist in {root!s}")
        return candidate
    if latest:
        return latest_run_dir(root)
    raise ValueError("must provide run_id or latest=True")


def summarize_run(run_dir: str | Path) -> dict[str, Any]:
    """Build a deterministic summary payload for one run directory."""
    run_path = Path(run_dir)
    run_meta = {}
    run_json = run_path / "run.json"
    if run_json.exists():
        run_meta = json.loads(run_json.read_text(encoding="utf-8"))

    tasks = read_jsonl(run_path / "tasks.jsonl")
    resources = read_jsonl(run_path / "resources.jsonl")
    workers = read_jsonl(run_path / "workers.jsonl")
    failures = read_jsonl(run_path / "failures.jsonl")
    caches = read_jsonl(run_path / "cache.jsonl")
    artifacts = read_jsonl(run_path / "artifacts.jsonl")
    costs = read_jsonl(run_path / "cost.jsonl")

    final_state_by_task: dict[str, str] = {}
    duration_values: list[float] = []
    for row in tasks:
        task_id = str(row.get("task_id", ""))
        state = str(row.get("state", "unknown"))
        if task_id:
            final_state_by_task[task_id] = state
        duration = row.get("duration_s")
        if isinstance(duration, (int, float)) and duration >= 0:
            duration_values.append(float(duration))

    state_counter = Counter(final_state_by_task.values())
    failure_counter = Counter(str(f.get("failure_class", "unknown")) for f in failures)
    cache_hits = sum(1 for c in caches if bool(c.get("hit")))
    cache_misses = sum(1 for c in caches if not bool(c.get("hit")))

    requested_cpus: list[int] = []
    for row in resources:
        value = row.get("requested_cpus")
        if isinstance(value, int):
            requested_cpus.append(value)

    # Cost summary
    cost_total_hourly = sum(float(c.get("total_hourly", 0)) for c in costs)
    cost_total_monthly = sum(float(c.get("total_monthly", 0)) for c in costs)

    return {
        "run": run_meta,
        "counts": {
            "task_events": len(tasks),
            "resource_events": len(resources),
            "worker_events": len(workers),
            "failure_events": len(failures),
            "cache_events": len(caches),
            "artifact_events": len(artifacts),
            "cost_events": len(costs),
            "tasks_succeeded": state_counter.get("succeeded", 0),
            "tasks_failed": state_counter.get("failed", 0),
            "tasks_cancelled": state_counter.get("cancelled", 0),
        },
        "timing": {
            "task_duration_count": len(duration_values),
            "task_duration_total_s": round(sum(duration_values), 6),
            "task_duration_avg_s": round(sum(duration_values) / len(duration_values), 6)
            if duration_values
            else None,
        },
        "cache": {
            "hits": cache_hits,
            "misses": cache_misses,
            "hit_ratio": round(cache_hits / (cache_hits + cache_misses), 6)
            if (cache_hits + cache_misses) > 0
            else None,
        },
        "resources": {
            "requested_cpu_min": min(requested_cpus) if requested_cpus else None,
            "requested_cpu_max": max(requested_cpus) if requested_cpus else None,
            "requested_cpu_avg": round(sum(requested_cpus) / len(requested_cpus), 6)
            if requested_cpus
            else None,
        },
        "cost": {
            "total_hourly_usd": round(cost_total_hourly, 6) if costs else None,
            "total_monthly_usd": round(cost_total_monthly, 4) if costs else None,
            "estimates_count": len(costs),
        },
        "failures": {
            "classes": dict(sorted(failure_counter.items())),
        },
    }


def render_text_report(summary: dict[str, Any]) -> str:
    """Render a concise human-readable report."""
    run = summary.get("run", {})
    counts = summary.get("counts", {})
    timing = summary.get("timing", {})
    cache = summary.get("cache", {})
    cost = summary.get("cost", {})

    lines = [
        f"run_id: {run.get('run_id', 'unknown')}",
        f"project: {run.get('project_name', 'unknown')}",
        f"target/provider: {run.get('target_name', 'unknown')}/{run.get('provider_name', 'unknown')}",
        f"status: {run.get('status', 'unknown')}",
        "",
        "tasks:",
        f"  succeeded: {counts.get('tasks_succeeded', 0)}",
        f"  failed: {counts.get('tasks_failed', 0)}",
        f"  cancelled: {counts.get('tasks_cancelled', 0)}",
        f"  event_rows: {counts.get('task_events', 0)}",
        "",
        "timing:",
        f"  total_s: {timing.get('task_duration_total_s')}",
        f"  avg_s: {timing.get('task_duration_avg_s')}",
        "",
        "cache:",
        f"  hits: {cache.get('hits', 0)}",
        f"  misses: {cache.get('misses', 0)}",
        f"  hit_ratio: {cache.get('hit_ratio')}",
    ]

    if cost.get("total_hourly_usd") is not None:
        lines.extend([
            "",
            "cost:",
            f"  hourly_usd: {cost.get('total_hourly_usd')}",
            f"  monthly_usd: {cost.get('total_monthly_usd')}",
        ])

    return "\n".join(lines)


__all__ = [
    "iter_run_dirs",
    "latest_run_dir",
    "read_jsonl",
    "render_text_report",
    "resolve_run_dir",
    "summarize_run",
]

