"""Unit tests for scalable run CLI verb."""

from __future__ import annotations

import os
import tempfile

import pytest

from scalable.cli.cmd_run import run_run


class TestRunCommand:
    def _write_manifest(self, tmp: str, content: str | None = None) -> str:
        """Write a minimal manifest and return its path."""
        path = os.path.join(tmp, "scalable.yaml")
        if content is None:
            content = """\
version: 1
project:
  name: test-run
targets:
  local:
    provider: local
components:
  model:
    cpus: 2
    memory: 4G
tasks:
  run_model:
    component: model
"""
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_dry_run_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self._write_manifest(tmp)
            rc = run_run(manifest_path, target="local", dry_run=True)
            assert rc == 0

    def test_no_workflow_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self._write_manifest(tmp)
            rc = run_run(manifest_path, target="local")
            assert rc == 0

    def test_missing_manifest(self):
        rc = run_run("/nonexistent/scalable.yaml", target="local")
        assert rc == 2

    def test_missing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self._write_manifest(tmp)
            rc = run_run(manifest_path, target="nonexistent")
            assert rc == 2

    def test_workflow_file_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self._write_manifest(tmp)
            rc = run_run(
                manifest_path,
                target="local",
                workflow="/nonexistent/workflow.py",
            )
            assert rc == 2

    def test_workflow_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = self._write_manifest(tmp)
            wf_path = os.path.join(tmp, "workflow.py")
            with open(wf_path, "w") as f:
                f.write("# Simple workflow\nresult = 1 + 1\n")
            rc = run_run(manifest_path, target="local", workflow=wf_path)
            assert rc == 0


class TestRunCLIIntegration:
    """Test the CLI dispatch for scalable run."""

    def test_run_in_parser(self):
        from scalable.cli.main import _build_parser

        parser = _build_parser()
        # Should not raise
        args = parser.parse_args(["run", "--dry-run"])
        assert args.command == "run"
        assert args.dry_run is True
