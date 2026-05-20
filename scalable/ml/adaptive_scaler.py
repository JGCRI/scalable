"""Real-time adaptive worker scaling based on ML predictions."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ScaleDecision:
    """A scaling recommendation with reasoning."""

    workers_to_add: dict[str, int]
    workers_to_remove: dict[str, int]
    reasoning: str
    confidence: float
    predicted_completion_time: float | None = None
    timestamp: float = field(default_factory=time.time)

    @property
    def has_changes(self) -> bool:
        """Whether this decision suggests any scaling changes."""
        return bool(self.workers_to_add or self.workers_to_remove)

    def to_dict(self) -> dict[str, Any]:
        return {
            "workers_to_add": dict(self.workers_to_add),
            "workers_to_remove": dict(self.workers_to_remove),
            "reasoning": self.reasoning,
            "confidence": self.confidence,
            "predicted_completion_time": self.predicted_completion_time,
            "timestamp": self.timestamp,
        }


class AdaptiveScaler:
    """Real-time adaptive worker scaling based on ML predictions.

    Monitors task queue depth and active worker utilization to recommend
    scaling actions. Respects user-defined min/max bounds and cooldown
    periods to prevent thrashing.

    Parameters
    ----------
    advisor
        A :class:`~scalable.ml.learned_advisor.LearnedAdvisor` or
        :class:`~scalable.advising.resources.ResourceAdvisor` instance
        for predicting task durations.
    min_workers
        Minimum worker count per tag (floor).
    max_workers
        Maximum worker count per tag (ceiling).
    scale_up_threshold
        Queue depth ratio that triggers scale-up (0.0–1.0).
    scale_down_threshold
        Queue depth ratio that triggers scale-down (0.0–1.0).
    cooldown_seconds
        Minimum time between scaling decisions.
    """

    def __init__(
        self,
        *,
        advisor: Any = None,
        min_workers: dict[str, int] | None = None,
        max_workers: dict[str, int] | None = None,
        scale_up_threshold: float = 0.8,
        scale_down_threshold: float = 0.2,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self._advisor = advisor
        self._min_workers = min_workers or {}
        self._max_workers = max_workers or {}
        self._scale_up_threshold = scale_up_threshold
        self._scale_down_threshold = scale_down_threshold
        self._cooldown_seconds = cooldown_seconds
        self._last_decision_time: float = 0.0
        self._decision_history: list[ScaleDecision] = []

    @property
    def decision_history(self) -> list[ScaleDecision]:
        """List of all scaling decisions made."""
        return list(self._decision_history)

    def evaluate(
        self,
        *,
        pending_tasks: list[dict[str, Any]],
        active_workers: dict[str, int],
        recent_completions: list[dict[str, Any]] | None = None,
    ) -> ScaleDecision:
        """Evaluate current state and recommend scaling actions.

        Parameters
        ----------
        pending_tasks
            List of pending task metadata dicts. Each should have at least
            ``tag`` or ``component`` key.
        active_workers
            Current worker count per tag/component.
        recent_completions
            Recently completed task metadata for throughput estimation.

        Returns
        -------
        ScaleDecision
            Recommended scaling action with reasoning.
        """
        now = time.time()

        # Check cooldown
        if now - self._last_decision_time < self._cooldown_seconds:
            return ScaleDecision(
                workers_to_add={},
                workers_to_remove={},
                reasoning="Cooldown period active",
                confidence=1.0,
                predicted_completion_time=None,
            )

        # Group pending tasks by tag/component
        pending_by_tag: dict[str, int] = {}
        for task in pending_tasks:
            tag = task.get("tag") or task.get("component") or "default"
            pending_by_tag[tag] = pending_by_tag.get(tag, 0) + 1

        workers_to_add: dict[str, int] = {}
        workers_to_remove: dict[str, int] = {}
        reasons: list[str] = []

        for tag, pending_count in pending_by_tag.items():
            current_workers = active_workers.get(tag, 0)
            max_allowed = self._max_workers.get(tag, current_workers + 10)
            min_allowed = self._min_workers.get(tag, 0)

            if current_workers == 0:
                # No workers — always scale up if there's pending work
                to_add = min(pending_count, max_allowed)
                if to_add > 0:
                    workers_to_add[tag] = to_add
                    reasons.append(f"{tag}: no workers, adding {to_add} for {pending_count} pending")
                continue

            # Calculate queue ratio (pending per worker)
            queue_ratio = pending_count / max(current_workers, 1)

            if queue_ratio > self._scale_up_threshold:
                # Scale up: add workers proportional to excess queue
                desired = min(
                    int(pending_count / self._scale_up_threshold),
                    max_allowed,
                )
                to_add = max(0, desired - current_workers)
                if to_add > 0:
                    workers_to_add[tag] = to_add
                    reasons.append(
                        f"{tag}: queue ratio {queue_ratio:.2f} > {self._scale_up_threshold}, "
                        f"adding {to_add} workers"
                    )

            elif queue_ratio < self._scale_down_threshold and current_workers > min_allowed:
                # Scale down: remove excess workers
                desired = max(
                    int(pending_count / self._scale_up_threshold) + 1,
                    min_allowed,
                )
                to_remove = max(0, current_workers - desired)
                if to_remove > 0:
                    workers_to_remove[tag] = to_remove
                    reasons.append(
                        f"{tag}: queue ratio {queue_ratio:.2f} < {self._scale_down_threshold}, "
                        f"removing {to_remove} workers"
                    )

        # Check for tags with workers but no pending tasks
        for tag, count in active_workers.items():
            if tag not in pending_by_tag and count > self._min_workers.get(tag, 0):
                excess = count - self._min_workers.get(tag, 0)
                if excess > 0:
                    workers_to_remove[tag] = excess
                    reasons.append(f"{tag}: no pending tasks, removing {excess} idle workers")

        # Estimate completion time
        predicted_completion = self._estimate_completion_time(
            pending_by_tag, active_workers, workers_to_add, recent_completions
        )

        reasoning = "; ".join(reasons) if reasons else "No scaling changes needed"
        confidence = 0.9 if self._advisor is not None else 0.7

        decision = ScaleDecision(
            workers_to_add=workers_to_add,
            workers_to_remove=workers_to_remove,
            reasoning=reasoning,
            confidence=confidence,
            predicted_completion_time=predicted_completion,
        )

        self._last_decision_time = now
        self._decision_history.append(decision)
        return decision

    def _estimate_completion_time(
        self,
        pending_by_tag: dict[str, int],
        active_workers: dict[str, int],
        workers_to_add: dict[str, int],
        recent_completions: list[dict[str, Any]] | None,
    ) -> float | None:
        """Estimate time to complete all pending tasks."""
        if not pending_by_tag:
            return 0.0

        if not recent_completions:
            return None

        # Simple throughput-based estimation
        total_pending = sum(pending_by_tag.values())
        total_workers = sum(active_workers.values()) + sum(workers_to_add.values())

        if total_workers == 0:
            return None

        # Estimate average task duration from recent completions
        durations = [
            c.get("duration_s", 60)
            for c in recent_completions
            if c.get("duration_s") is not None
        ]
        if not durations:
            return None

        avg_duration = sum(durations) / len(durations)
        estimated_time = (total_pending / total_workers) * avg_duration
        return estimated_time

    def reset_cooldown(self) -> None:
        """Reset the cooldown timer (for testing or manual override)."""
        self._last_decision_time = 0.0


__all__ = ["AdaptiveScaler", "ScaleDecision"]
