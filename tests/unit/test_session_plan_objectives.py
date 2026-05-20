"""Unit tests for ScalableSession.plan(objective=, policy=) Phase 4 implementation."""

from __future__ import annotations

import pytest
import yaml

from scalable.session.session import ScalableSession


def _make_manifest(tmp_path):
    """Create a minimal test manifest for session testing."""
    manifest_content = {
        "version": 1,
        "project": {"name": "test-project"},
        "targets": {
            "local": {"provider": "local", "max_workers": 4},
        },
        "components": {
            "model_a": {"cpus": 4, "memory": "16G", "tags": ["compute"]},
            "model_b": {"cpus": 2, "memory": "8G", "tags": ["io"]},
        },
        "tasks": {
            "run_a": {"component": "model_a", "cache": True},
            "run_b": {"component": "model_b"},
        },
    }
    manifest_path = tmp_path / "scalable.yaml"
    manifest_path.write_text(yaml.dump(manifest_content))
    return manifest_path


class TestSessionPlanObjectives:
    def test_plan_no_objective_works(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        session = ScalableSession.from_yaml(manifest_path, target="local")
        plan = session.plan(dry_run=True)
        assert plan.target_name == "local"
        assert plan.scale_plan.workers_by_tag

    def test_plan_minimize_cost_safe(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        session = ScalableSession.from_yaml(manifest_path, target="local")
        plan = session.plan(dry_run=True, objective="minimize cost", policy="safe")
        # Workers should be conservative
        for _tag, count in plan.scale_plan.workers_by_tag.items():
            assert count >= 1

    def test_plan_minimize_time_aggressive(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        session = ScalableSession.from_yaml(manifest_path, target="local")
        plan = session.plan(dry_run=True, objective="minimize time", policy="aggressive")
        # Should scale up workers
        base_plan = session.plan(dry_run=True)
        for tag in plan.scale_plan.workers_by_tag:
            assert plan.scale_plan.workers_by_tag[tag] >= base_plan.scale_plan.workers_by_tag[tag]

    def test_plan_balance_default(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        session = ScalableSession.from_yaml(manifest_path, target="local")
        plan = session.plan(dry_run=True, objective="balance")
        assert plan.target_name == "local"

    def test_plan_manual_policy(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        session = ScalableSession.from_yaml(manifest_path, target="local")
        base_plan = session.plan(dry_run=True)
        manual_plan = session.plan(dry_run=True, objective="minimize cost", policy="manual")
        # Manual policy should match base plan exactly
        assert manual_plan.scale_plan.workers_by_tag == base_plan.scale_plan.workers_by_tag

    def test_unsupported_objective_raises(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        session = ScalableSession.from_yaml(manifest_path, target="local")
        with pytest.raises(NotImplementedError, match="Unsupported objective"):
            session.plan(dry_run=True, objective="do magic")

    def test_unsupported_policy_raises(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        session = ScalableSession.from_yaml(manifest_path, target="local")
        with pytest.raises(NotImplementedError, match="Unsupported policy"):
            session.plan(dry_run=True, objective="balance", policy="yolo")

    def test_objective_only_uses_safe_default(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        session = ScalableSession.from_yaml(manifest_path, target="local")
        # Should not raise - uses "safe" default policy
        plan = session.plan(dry_run=True, objective="minimize cost")
        assert plan is not None

    def test_policy_only_uses_balance_default(self, tmp_path):
        manifest_path = _make_manifest(tmp_path)
        session = ScalableSession.from_yaml(manifest_path, target="local")
        # Should not raise - uses "balance" default objective
        plan = session.plan(dry_run=True, policy="safe")
        assert plan is not None
