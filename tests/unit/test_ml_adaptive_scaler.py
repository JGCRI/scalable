"""Tests for scalable.ml.adaptive_scaler — adaptive scaling policy."""

from __future__ import annotations

import pytest

from scalable.ml.adaptive_scaler import AdaptiveScaler, ScaleDecision


class TestScaleDecision:
    def test_no_changes(self):
        d = ScaleDecision(
            workers_to_add={},
            workers_to_remove={},
            reasoning="no changes",
            confidence=0.9,
        )
        assert not d.has_changes

    def test_has_changes_add(self):
        d = ScaleDecision(
            workers_to_add={"gcam": 2},
            workers_to_remove={},
            reasoning="scale up",
            confidence=0.8,
        )
        assert d.has_changes

    def test_to_dict(self):
        d = ScaleDecision(
            workers_to_add={"gcam": 1},
            workers_to_remove={"stitches": 1},
            reasoning="rebalance",
            confidence=0.85,
            predicted_completion_time=300.0,
        )
        result = d.to_dict()
        assert result["workers_to_add"] == {"gcam": 1}
        assert result["confidence"] == 0.85


class TestAdaptiveScaler:
    def test_cooldown_blocks_rapid_decisions(self):
        scaler = AdaptiveScaler(cooldown_seconds=60.0)
        # First evaluation
        decision1 = scaler.evaluate(
            pending_tasks=[{"tag": "gcam"}],
            active_workers={"gcam": 0},
        )
        assert decision1.has_changes

        # Second evaluation within cooldown
        decision2 = scaler.evaluate(
            pending_tasks=[{"tag": "gcam"}],
            active_workers={"gcam": 1},
        )
        assert not decision2.has_changes
        assert "Cooldown" in decision2.reasoning

    def test_scale_up_on_high_queue(self):
        scaler = AdaptiveScaler(
            scale_up_threshold=0.8,
            cooldown_seconds=0,
        )
        decision = scaler.evaluate(
            pending_tasks=[{"tag": "gcam"}] * 10,
            active_workers={"gcam": 2},
        )
        assert decision.workers_to_add.get("gcam", 0) > 0

    def test_scale_down_on_low_queue(self):
        scaler = AdaptiveScaler(
            scale_down_threshold=0.2,
            cooldown_seconds=0,
            min_workers={"gcam": 1},
        )
        decision = scaler.evaluate(
            pending_tasks=[],  # No pending tasks
            active_workers={"gcam": 5},
        )
        assert decision.workers_to_remove.get("gcam", 0) > 0

    def test_respects_max_workers(self):
        scaler = AdaptiveScaler(
            max_workers={"gcam": 3},
            cooldown_seconds=0,
        )
        decision = scaler.evaluate(
            pending_tasks=[{"tag": "gcam"}] * 100,
            active_workers={"gcam": 0},
        )
        assert decision.workers_to_add.get("gcam", 0) <= 3

    def test_respects_min_workers(self):
        scaler = AdaptiveScaler(
            min_workers={"gcam": 2},
            cooldown_seconds=0,
        )
        decision = scaler.evaluate(
            pending_tasks=[],
            active_workers={"gcam": 5},
        )
        # Should not remove below minimum
        removed = decision.workers_to_remove.get("gcam", 0)
        remaining = 5 - removed
        assert remaining >= 2

    def test_no_workers_triggers_scaleup(self):
        scaler = AdaptiveScaler(cooldown_seconds=0)
        decision = scaler.evaluate(
            pending_tasks=[{"tag": "gcam"}, {"tag": "gcam"}],
            active_workers={"gcam": 0},
        )
        assert decision.workers_to_add.get("gcam", 0) > 0

    def test_completion_time_estimation(self):
        scaler = AdaptiveScaler(cooldown_seconds=0)
        decision = scaler.evaluate(
            pending_tasks=[{"tag": "gcam"}] * 4,
            active_workers={"gcam": 2},
            recent_completions=[
                {"duration_s": 60},
                {"duration_s": 80},
            ],
        )
        assert decision.predicted_completion_time is not None

    def test_reset_cooldown(self):
        scaler = AdaptiveScaler(cooldown_seconds=9999)
        scaler.evaluate(
            pending_tasks=[{"tag": "x"}],
            active_workers={"x": 0},
        )
        scaler.reset_cooldown()
        decision = scaler.evaluate(
            pending_tasks=[{"tag": "x"}],
            active_workers={"x": 0},
        )
        assert decision.has_changes

    def test_decision_history(self):
        scaler = AdaptiveScaler(cooldown_seconds=0)
        scaler.evaluate(
            pending_tasks=[{"tag": "a"}],
            active_workers={"a": 0},
        )
        assert len(scaler.decision_history) == 1
