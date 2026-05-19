"""Unit tests for ``scalable report`` CLI behavior."""

from __future__ import annotations

import json
from pathlib import Path

from scalable.cli.main import main


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
    (run_dir / "tasks.jsonl").write_text(
        json.dumps(
            {
                "task_id": "t1",
                "task_name": "run_gcam",
                "component": "gcam",
                "state": "succeeded",
                "duration_s": 1.5,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_cli_report_latest_text(tmp_path: Path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "run-20260519T120000Z-demo-aaaa1111"
    _seed_run(run_dir)

    code = main(["report", "--runs-dir", str(runs_dir), "--latest"])

    captured = capsys.readouterr()
    assert code == 0
    assert "run_id:" in captured.out
    assert run_dir.name in captured.out


def test_cli_report_json_and_output_file(tmp_path: Path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    run_dir = runs_dir / "run-20260519T120000Z-demo-aaaa1111"
    _seed_run(run_dir)
    output = tmp_path / "report.json"

    code = main(
        [
            "report",
            "--runs-dir",
            str(runs_dir),
            "--run-id",
            run_dir.name,
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    file_payload = json.loads(output.read_text(encoding="utf-8"))

    assert code == 0
    assert payload["run"]["run_id"] == run_dir.name
    assert file_payload == payload


def test_cli_report_missing_selection_returns_error(tmp_path: Path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    code = main(["report", "--runs-dir", str(runs_dir)])
    captured = capsys.readouterr()

    assert code == 1
    assert "report failed" in captured.err

