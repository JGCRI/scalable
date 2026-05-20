"""CLI command: ``scalable advise`` — ML-backed resource recommendations."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def register_advise_parser(subparsers: Any) -> None:
    """Register the ``advise`` subcommand."""
    parser = subparsers.add_parser(
        "advise",
        help="Get ML-backed resource recommendations for a task",
        description=(
            "Analyze telemetry history and provide ML-backed resource "
            "recommendations. Falls back to heuristic quantiles when "
            "insufficient data or scalable[ml] is not installed."
        ),
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Task name to get recommendations for",
    )
    parser.add_argument(
        "--target",
        default=None,
        help="Deployment target to scope recommendations",
    )
    parser.add_argument(
        "--runs-dir",
        default=None,
        help="Path to runs directory (default: .scalable/runs)",
    )
    parser.add_argument(
        "--model-type",
        default="gradient_boosting",
        choices=["gradient_boosting", "random_forest", "quantile_regression"],
        help="ML model type for predictions (default: gradient_boosting)",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.95,
        help="Confidence level for recommendations (default: 0.95)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="output_format",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path (default: stdout)",
    )
    parser.set_defaults(func=_run_advise)


def _run_advise(args: argparse.Namespace) -> int:
    """Execute the advise command."""
    from scalable.common import settings

    runs_dir = args.runs_dir or settings.runs_dir

    # Try ML advisor first, fall back to heuristic
    recommendation = None
    method = "heuristic"

    try:
        from scalable.ml.learned_advisor import LearnedAdvisor

        advisor = LearnedAdvisor.from_history(
            runs_dir,
            model_type=args.model_type,
        )
        recommendation = advisor.recommend(
            task=args.task,
            target=args.target,
            confidence=args.confidence,
        )
        method = recommendation.evidence.get("method", "ml")
    except (ImportError, Exception):
        # Fall back to Phase 2 heuristic advisor
        try:
            from scalable.advising.resources import ResourceAdvisor

            advisor_h = ResourceAdvisor.from_history(runs_dir)
            recommendation = advisor_h.recommend(
                task=args.task,
                target=args.target,
                confidence=args.confidence,
            )
            method = "heuristic"
        except Exception as e:
            sys.stderr.write(f"Error: Could not load run history: {e}\n")
            return 1

    if recommendation is None:
        sys.stderr.write("Error: No recommendation could be generated\n")
        return 1

    # Format output
    if args.output_format == "json":
        output = json.dumps(
            {
                "task": recommendation.task,
                "target": recommendation.target,
                "confidence": recommendation.confidence,
                "method": method,
                "workers": recommendation.workers,
                "resources": recommendation.resources,
                "evidence": recommendation.evidence,
            },
            indent=2,
        )
    else:
        output = _format_text(recommendation, method)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output + "\n")
    else:
        sys.stdout.write(output + "\n")

    return 0


def _format_text(recommendation: Any, method: str) -> str:
    """Format recommendation as human-readable text."""
    lines = [
        f"Resource Recommendation for: {recommendation.task}",
        f"{'=' * 50}",
        f"Method: {method}",
        f"Confidence: {recommendation.confidence:.2f}",
        f"Target: {recommendation.target or 'any'}",
        "",
        "Workers:",
    ]

    for tag, count in recommendation.workers.items():
        lines.append(f"  {tag}: {count}")

    lines.append("")
    lines.append("Resources:")
    for tag, res in recommendation.resources.items():
        lines.append(f"  {tag}:")
        lines.append(f"    CPUs: {res.get('cpus', 'N/A')}")
        lines.append(f"    Memory: {res.get('memory', 'N/A')}")
        lines.append(f"    Walltime: {res.get('walltime', 'N/A')}")

    if recommendation.evidence:
        lines.append("")
        lines.append("Evidence:")
        records = recommendation.evidence.get("records", 0)
        lines.append(f"  Historical records: {records}")
        if "predicted_duration_s" in recommendation.evidence:
            dur = recommendation.evidence["predicted_duration_s"]
            lines.append(f"  Predicted duration: {dur:.1f}s")
        if "feature_importances" in recommendation.evidence:
            importances = recommendation.evidence["feature_importances"]
            if importances:
                lines.append("  Top features:")
                sorted_features = sorted(
                    importances.items(), key=lambda x: x[1], reverse=True
                )[:5]
                for feat, imp in sorted_features:
                    lines.append(f"    {feat}: {imp:.3f}")

    return "\n".join(lines)
