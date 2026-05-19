"""Unit tests for ``scalable plan`` CLI behavior."""

from __future__ import annotations

import json
from pathlib import Path

from scalable.cli.main import main


def _write_valid_manifest(path: Path) -> None:
    path.write_text(
        """
version: 1
project:
  name: demo
targets:
  local:
    provider: local
    max_workers: 1
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


def test_cli_plan_dry_run_writes_plan_and_manifest_lock(tmp_path: Path, capsys) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    _write_valid_manifest(manifest_path)
    output_path = tmp_path / "plan.json"

    code = main(
        [
            "plan",
            str(manifest_path),
            "--target",
            "local",
            "--dry-run",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    lock_path = tmp_path / "manifest.lock"

    assert code == 0
    assert payload["target"] == "local"
    assert file_payload == payload
    assert lock_path.exists()
    assert len(lock_path.read_text(encoding="utf-8").strip()) == 64


def test_cli_plan_requires_dry_run_flag(tmp_path: Path, capsys) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    _write_valid_manifest(manifest_path)
    output_path = tmp_path / "plan.json"

    code = main(["plan", str(manifest_path), "--output", str(output_path)])

    captured = capsys.readouterr()
    assert code == 2
    assert "supports dry-run" in captured.err
    assert not output_path.exists()


def test_cli_plan_invalid_manifest_returns_nonzero(tmp_path: Path, capsys) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    _write_valid_manifest(manifest_path)
    text = manifest_path.read_text(encoding="utf-8")
    text = text.replace("component: gcam", "component: missing_component")
    manifest_path.write_text(text, encoding="utf-8")

    code = main(["plan", str(manifest_path), "--dry-run"])

    captured = capsys.readouterr()
    assert code == 1
    assert "planning failed" in captured.err

