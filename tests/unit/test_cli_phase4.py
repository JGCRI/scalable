"""Unit tests for Phase 4 CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from scalable.cli.main import main


class TestCliInitComponent:
    def test_init_component_basic(self, tmp_path, capsys):
        model_dir = tmp_path / "mymodel"
        model_dir.mkdir()
        (model_dir / "main.py").write_text("print('hello')")
        (model_dir / "requirements.txt").write_text("numpy")

        exit_code = main(["init-component", str(model_dir), "--no-ai"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "mymodel" in captured.out

    def test_init_component_with_name(self, tmp_path, capsys):
        model_dir = tmp_path / "src"
        model_dir.mkdir()
        (model_dir / "app.py").write_text("pass")

        exit_code = main(["init-component", str(model_dir), "--name", "custom-name", "--no-ai"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "custom-name" in captured.out

    def test_init_component_output_file(self, tmp_path, capsys):
        model_dir = tmp_path / "model"
        model_dir.mkdir()
        (model_dir / "run.py").write_text("pass")
        output_file = tmp_path / "component.yaml"

        exit_code = main([
            "init-component", str(model_dir),
            "--output", str(output_file),
            "--no-ai",
        ])
        assert exit_code == 0
        assert output_file.exists()

    def test_init_component_nonexistent_dir(self, capsys):
        exit_code = main(["init-component", "/nonexistent/path", "--no-ai"])
        assert exit_code == 1


class TestCliDiagnose:
    def _create_run(self, tmp_path):
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir()
        run_dir = runs_dir / "run-20260519T120000Z-test-abc"
        run_dir.mkdir()
        (run_dir / "run.json").write_text(json.dumps({
            "run_id": "run-20260519T120000Z-test-abc",
            "project_name": "test",
            "target_name": "local",
            "provider_name": "local",
            "manifest_lock": "abc123",
            "status": "failed",
        }))
        (run_dir / "failures.jsonl").write_text(json.dumps({
            "failure_class": "MemoryError",
            "message": "out of memory",
            "task_id": "t1",
        }))
        (run_dir / "tasks.jsonl").write_text(json.dumps({
            "task_id": "t1",
            "state": "failed",
            "task_name": "run_gcam",
        }))
        return runs_dir

    def test_diagnose_latest(self, tmp_path, capsys):
        runs_dir = self._create_run(tmp_path)
        exit_code = main([
            "diagnose", "--runs-dir", str(runs_dir), "--latest", "--no-ai",
        ])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "oom" in captured.out.lower() or "Diagnosis" in captured.out

    def test_diagnose_json_format(self, tmp_path, capsys):
        runs_dir = self._create_run(tmp_path)
        exit_code = main([
            "diagnose", "--runs-dir", str(runs_dir),
            "--latest", "--format", "json", "--no-ai",
        ])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "classifications" in data

    def test_diagnose_no_runs(self, tmp_path, capsys):
        empty_dir = tmp_path / "empty_runs"
        empty_dir.mkdir()
        exit_code = main([
            "diagnose", "--runs-dir", str(empty_dir), "--latest", "--no-ai",
        ])
        assert exit_code == 1


class TestCliExplain:
    def test_explain_plan(self, tmp_path, capsys):
        plan = {
            "version": 1,
            "target": "local",
            "provider": "local",
            "manifest_lock": "abc123",
            "task_to_component": {"run_model": "model"},
            "scale_plan": {
                "workers_by_tag": {"model": 1},
                "resources_by_tag": {"model": {"cpus": 2, "memory": "8G", "walltime": None, "gpus": None}},
            },
        }
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan))

        exit_code = main(["explain", str(plan_file), "--no-ai"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Plan Explanation" in captured.out

    def test_explain_missing_file(self, tmp_path, capsys):
        exit_code = main(["explain", str(tmp_path / "no.json"), "--no-ai"])
        assert exit_code == 1

    def test_explain_json_format(self, tmp_path, capsys):
        plan = {
            "version": 1, "target": "local", "provider": "local",
            "manifest_lock": "x", "task_to_component": {},
            "scale_plan": {"workers_by_tag": {}, "resources_by_tag": {}},
        }
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(plan))

        exit_code = main(["explain", str(plan_file), "--format", "json", "--no-ai"])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "narrative" in data


class TestCliCompose:
    def test_compose_known_model(self, capsys):
        exit_code = main(["compose", "Run GCAM reference scenario", "--no-ai"])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "workflow.py" in captured.out or "gcam" in captured.out.lower()

    def test_compose_with_output_dir(self, tmp_path, capsys):
        output_dir = tmp_path / "generated"
        exit_code = main([
            "compose", "Run GCAM and Stitches",
            "--output-dir", str(output_dir),
            "--no-ai",
        ])
        assert exit_code == 0
        assert (output_dir / "workflow.py").exists()

    def test_compose_json_format(self, capsys):
        exit_code = main([
            "compose", "Run Hector model",
            "--format", "json", "--no-ai",
        ])
        assert exit_code == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "files" in data


class TestCliMigrate:
    def test_migrate_to_kubernetes(self, tmp_path, capsys):
        manifest = {
            "version": 1,
            "project": {"name": "test"},
            "targets": {"local": {"provider": "local"}},
            "components": {"comp": {"cpus": 2, "memory": "8G"}},
            "tasks": {"t1": {"component": "comp"}},
        }
        manifest_path = tmp_path / "scalable.yaml"
        manifest_path.write_text(yaml.dump(manifest))

        exit_code = main([
            "migrate", str(manifest_path),
            "--to-provider", "kubernetes",
            "--no-ai",
        ])
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "kubernetes" in captured.out.lower()

    def test_migrate_no_goal_errors(self, tmp_path, capsys):
        manifest = {
            "version": 1,
            "project": {"name": "test"},
            "targets": {"local": {"provider": "local"}},
            "components": {},
            "tasks": {},
        }
        manifest_path = tmp_path / "scalable.yaml"
        manifest_path.write_text(yaml.dump(manifest))

        exit_code = main(["migrate", str(manifest_path), "--no-ai"])
        assert exit_code == 1

    def test_migrate_nonexistent_manifest(self, tmp_path, capsys):
        exit_code = main([
            "migrate", str(tmp_path / "no.yaml"),
            "--to-provider", "aws", "--no-ai",
        ])
        assert exit_code == 1
