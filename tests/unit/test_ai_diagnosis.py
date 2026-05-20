"""Unit tests for scalable.ai.log_diagnosis module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scalable.ai.log_diagnosis import DiagnosisResult, diagnose_run


def _create_run_dir(tmp_path, *, failures=None, tasks=None, resources=None, run_meta=None):
    """Helper to create a synthetic run directory."""
    run_dir = tmp_path / "run-20260519T120000Z-test-12345678"
    run_dir.mkdir(parents=True)

    meta = run_meta or {
        "run_id": "run-20260519T120000Z-test-12345678",
        "project_name": "test",
        "target_name": "local",
        "provider_name": "local",
        "manifest_lock": "abc123",
        "status": "failed",
    }
    (run_dir / "run.json").write_text(json.dumps(meta))

    if failures:
        lines = [json.dumps(f) for f in failures]
        (run_dir / "failures.jsonl").write_text("\n".join(lines))

    if tasks:
        lines = [json.dumps(t) for t in tasks]
        (run_dir / "tasks.jsonl").write_text("\n".join(lines))

    if resources:
        lines = [json.dumps(r) for r in resources]
        (run_dir / "resources.jsonl").write_text("\n".join(lines))

    return run_dir


class TestDiagnoseRun:
    def test_nonexistent_run_dir(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            diagnose_run(run_dir=tmp_path / "nonexistent")

    def test_run_with_no_failures(self, tmp_path):
        run_dir = _create_run_dir(
            tmp_path,
            tasks=[
                {"task_id": "t1", "state": "succeeded", "task_name": "run_model"},
            ],
        )
        result = diagnose_run(run_dir=run_dir, no_ai=True)
        assert isinstance(result, DiagnosisResult)
        assert result.classifications == []
        assert "No failures" in result.summary

    def test_oom_failure_diagnosis(self, tmp_path):
        run_dir = _create_run_dir(
            tmp_path,
            failures=[
                {
                    "failure_class": "RuntimeError",
                    "message": "Worker killed with signal 9 (SIGKILL) - out of memory",
                    "task_id": "t1",
                }
            ],
            tasks=[
                {"task_id": "t1", "state": "failed", "task_name": "run_gcam",
                 "error_type": "RuntimeError", "error_message": "OOM"},
            ],
            resources=[
                {"entity_type": "task", "entity_id": "t1",
                 "requested_cpus": 6, "requested_memory": "8G"},
            ],
        )

        result = diagnose_run(run_dir=run_dir, no_ai=True)
        assert len(result.classifications) >= 1
        assert result.classifications[0].failure_class == "oom"
        assert result.classifications[0].confidence in ("medium", "high")
        assert len(result.classifications[0].suggested_fixes) > 0

    def test_walltime_failure_diagnosis(self, tmp_path):
        run_dir = _create_run_dir(
            tmp_path,
            failures=[
                {
                    "failure_class": "TimeoutError",
                    "message": "JOB CANCELLED DUE TO TIME LIMIT",
                    "task_id": "t1",
                }
            ],
        )

        result = diagnose_run(run_dir=run_dir, no_ai=True)
        assert result.classifications[0].failure_class == "walltime"

    def test_import_error_diagnosis(self, tmp_path):
        run_dir = _create_run_dir(
            tmp_path,
            failures=[
                {
                    "failure_class": "ModuleNotFoundError",
                    "message": "No module named 'scipy'",
                    "task_id": "t1",
                }
            ],
        )

        result = diagnose_run(run_dir=run_dir, no_ai=True)
        assert result.classifications[0].failure_class == "import_error"

    def test_task_summary_counts(self, tmp_path):
        run_dir = _create_run_dir(
            tmp_path,
            tasks=[
                {"task_id": "t1", "state": "succeeded", "task_name": "a"},
                {"task_id": "t2", "state": "succeeded", "task_name": "b"},
                {"task_id": "t3", "state": "failed", "task_name": "c",
                 "error_type": "Error", "error_message": "OOM"},
            ],
            failures=[
                {"failure_class": "Error", "message": "OOM", "task_id": "t3"}
            ],
        )

        result = diagnose_run(run_dir=run_dir, no_ai=True)
        assert result.task_summary.get("succeeded", 0) == 2
        assert result.task_summary.get("failed", 0) == 1

    def test_render_text_output(self, tmp_path):
        run_dir = _create_run_dir(
            tmp_path,
            failures=[
                {
                    "failure_class": "MemoryError",
                    "message": "out of memory",
                    "task_id": "t1",
                }
            ],
        )

        result = diagnose_run(run_dir=run_dir, no_ai=True)
        text = result.render_text()
        assert "Diagnosis" in text
        assert "oom" in text.lower() or "memory" in text.lower()

    def test_to_dict_serializable(self, tmp_path):
        run_dir = _create_run_dir(
            tmp_path,
            failures=[
                {"failure_class": "Error", "message": "test error"}
            ],
        )

        result = diagnose_run(run_dir=run_dir, no_ai=True)
        d = result.to_dict()
        # Should be JSON-serializable
        serialized = json.dumps(d)
        assert "classifications" in serialized

    def test_diagnose_latest(self, tmp_path):
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        run_dir = runs_dir / "run-20260519T120000Z-test-abc"
        run_dir.mkdir()
        (run_dir / "run.json").write_text(json.dumps({
            "run_id": "run-20260519T120000Z-test-abc",
            "project_name": "test",
            "target_name": "local",
            "provider_name": "local",
            "manifest_lock": "abc",
            "status": "completed",
        }))

        result = diagnose_run(runs_dir=runs_dir, latest=True, no_ai=True)
        assert result.run_id == "run-20260519T120000Z-test-abc"
