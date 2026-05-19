"""Unit tests for scalable.ai.plan_explain module."""

from __future__ import annotations

import json

import pytest

from scalable.ai.plan_explain import ExplanationResult, explain_plan


SAMPLE_PLAN = {
    "version": 1,
    "target": "local",
    "provider": "local",
    "manifest_lock": "abc123def456789",
    "task_to_component": {
        "run_gcam": "gcam",
        "run_stitches": "stitches",
    },
    "scale_plan": {
        "workers_by_tag": {
            "gcam": 2,
            "stitches": 1,
        },
        "resources_by_tag": {
            "gcam": {"cpus": 6, "memory": "20G", "walltime": "02:00:00", "gpus": None},
            "stitches": {"cpus": 1, "memory": "50G", "walltime": None, "gpus": None},
        },
    },
}


class TestExplainPlan:
    def test_explain_from_dict(self):
        result = explain_plan(plan_data=SAMPLE_PLAN, no_ai=True)
        assert isinstance(result, ExplanationResult)
        assert result.method == "heuristic"
        assert "gcam" in result.narrative
        assert "stitches" in result.narrative

    def test_explain_from_file(self, tmp_path):
        plan_file = tmp_path / "plan.json"
        plan_file.write_text(json.dumps(SAMPLE_PLAN))

        result = explain_plan(plan_path=plan_file, no_ai=True)
        assert result.plan_source == str(plan_file)
        assert "local" in result.narrative

    def test_explain_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            explain_plan(plan_path=tmp_path / "nonexistent.json", no_ai=True)

    def test_explain_no_input_raises(self):
        with pytest.raises(ValueError, match="Must provide"):
            explain_plan(no_ai=True)

    def test_sections_populated(self):
        result = explain_plan(plan_data=SAMPLE_PLAN, no_ai=True)
        assert "overview" in result.sections
        assert "resources" in result.sections
        assert "strategy" in result.sections
        assert "recommendations" in result.sections

    def test_overview_contains_tasks(self):
        result = explain_plan(plan_data=SAMPLE_PLAN, no_ai=True)
        assert "run_gcam" in result.sections["overview"]
        assert "run_stitches" in result.sections["overview"]

    def test_resources_section_details(self):
        result = explain_plan(plan_data=SAMPLE_PLAN, no_ai=True)
        assert "Workers: 2" in result.sections["resources"]
        assert "20G" in result.sections["resources"]

    def test_render_text(self):
        result = explain_plan(plan_data=SAMPLE_PLAN, no_ai=True)
        text = result.render_text()
        assert "Plan Explanation" in text

    def test_to_dict_serializable(self):
        result = explain_plan(plan_data=SAMPLE_PLAN, no_ai=True)
        d = result.to_dict()
        serialized = json.dumps(d)
        assert "narrative" in serialized

    def test_empty_plan(self):
        empty_plan = {
            "version": 1,
            "target": "local",
            "provider": "local",
            "manifest_lock": "abc",
            "task_to_component": {},
            "scale_plan": {
                "workers_by_tag": {},
                "resources_by_tag": {},
            },
        }
        result = explain_plan(plan_data=empty_plan, no_ai=True)
        assert "no workers" in result.sections["recommendations"].lower() or result.narrative
