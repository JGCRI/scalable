"""Unit tests for ``scalable validate`` CLI behavior."""

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


def test_cli_validate_valid_manifest_returns_zero(tmp_path: Path, capsys) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    _write_valid_manifest(manifest_path)

    code = main(["validate", str(manifest_path), "--target", "local"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 0
    assert payload["ok"] is True
    assert payload["errors"] == []


def test_cli_validate_invalid_manifest_returns_nonzero(tmp_path: Path, capsys) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    _write_valid_manifest(manifest_path)
    text = manifest_path.read_text(encoding="utf-8")
    text = text.replace("component: gcam", "component: missing_component")
    manifest_path.write_text(text, encoding="utf-8")

    code = main(["validate", str(manifest_path), "--target", "local"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 1
    assert payload["ok"] is False
    assert any(err["path"] == "tasks.run_gcam.component" for err in payload["errors"])


def test_cli_validate_schema_error_returns_nonzero(tmp_path: Path, capsys) -> None:
    manifest_path = tmp_path / "scalable.yaml"
    manifest_path.write_text("version: 1\n", encoding="utf-8")

    code = main(["validate", str(manifest_path)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert code == 1
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "E_MANIFEST"


def test_cli_stub_command_returns_pointer_message(capsys) -> None:
    code = main(["diagnose"])

    captured = capsys.readouterr()
    assert code == 2
    assert "planned for Phase 4" in captured.err

