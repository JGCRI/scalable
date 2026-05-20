"""``scalable`` console entry-point dispatcher.

Implemented subcommands:

* ``scalable validate``
* ``scalable plan --dry-run``
* ``scalable report``
* ``scalable run``
* ``scalable init-component``
* ``scalable diagnose``
* ``scalable explain``
* ``scalable compose``
* ``scalable migrate``

"""

from __future__ import annotations

import argparse
import sys

from scalable.common import settings

from .cmd_compose import run_compose
from .cmd_diagnose import run_diagnose
from .cmd_explain import run_explain
from .cmd_init_component import run_init_component
from .cmd_migrate import run_migrate
from .cmd_plan import run_plan
from .cmd_report import run_report
from .cmd_run import run_run
from .cmd_validate import run_validate

_STUB_COMMANDS: dict[str, str] = {}


def _handle_validate(args: argparse.Namespace) -> int:
    return run_validate(args.manifest, target=args.target)


def _handle_plan(args: argparse.Namespace) -> int:
    return run_plan(
        args.manifest,
        target=args.target,
        dry_run=bool(args.dry_run),
        output=args.output,
    )


def _handle_report(args: argparse.Namespace) -> int:
    return run_report(
        runs_dir=args.runs_dir,
        run_id=args.run_id,
        latest=bool(args.latest),
        fmt=args.format,
        output=args.output,
    )


def _handle_run(args: argparse.Namespace) -> int:
    return run_run(
        args.manifest,
        target=args.target,
        workflow=args.workflow,
        dry_run=bool(args.dry_run),
    )


def _handle_init_component(args: argparse.Namespace) -> int:
    return run_init_component(
        args.path,
        name=args.name,
        output=args.output,
        no_ai=bool(args.no_ai),
    )


def _handle_diagnose(args: argparse.Namespace) -> int:
    return run_diagnose(
        runs_dir=args.runs_dir,
        run_id=args.run_id,
        latest=bool(args.latest),
        fmt=args.format,
        output=args.output,
        no_ai=bool(args.no_ai),
    )


def _handle_explain(args: argparse.Namespace) -> int:
    return run_explain(
        args.plan,
        runs_dir=args.runs_dir,
        fmt=args.format,
        output=args.output,
        no_ai=bool(args.no_ai),
    )


def _handle_compose(args: argparse.Namespace) -> int:
    return run_compose(
        args.description,
        output_dir=args.output_dir,
        fmt=args.format,
        no_ai=bool(args.no_ai),
    )


def _handle_migrate(args: argparse.Namespace) -> int:
    return run_migrate(
        args.manifest,
        to_provider=args.to_provider,
        to_version=int(args.to_version) if args.to_version else None,
        goal=args.goal,
        fmt=args.format,
        output=args.output,
        no_ai=bool(args.no_ai),
    )


def _make_stub_handler(command: str, phase: str):
    def _handler(_: argparse.Namespace) -> int:
        print(
            f"scalable {command}: not yet available; planned for {phase}.",
            file=sys.stderr,
        )
        return 2

    return _handler


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scalable")
    subparsers = parser.add_subparsers(dest="command")

    # --- validate ---
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a scalable.yaml manifest and print a structured report",
    )
    validate_parser.add_argument(
        "manifest",
        nargs="?",
        default=settings.manifest_path,
        help="Path to scalable.yaml (default: SCALABLE_MANIFEST or ./scalable.yaml)",
    )
    validate_parser.add_argument(
        "--target",
        default=None,
        help="Optional target name override (default: manifest auto resolution)",
    )
    validate_parser.set_defaults(handler=_handle_validate)

    # --- plan ---
    plan_parser = subparsers.add_parser(
        "plan",
        help="Build a provider-neutral execution plan from a manifest",
    )
    plan_parser.add_argument(
        "manifest",
        nargs="?",
        default=settings.manifest_path,
        help="Path to scalable.yaml (default: SCALABLE_MANIFEST or ./scalable.yaml)",
    )
    plan_parser.add_argument(
        "--target",
        default=None,
        help="Optional target name override (default: manifest auto resolution)",
    )
    plan_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Required in Phase 1. Non-dry planning is not implemented yet.",
    )
    plan_parser.add_argument(
        "--output",
        default="plan.json",
        help="Plan output path (default: ./plan.json)",
    )
    plan_parser.set_defaults(handler=_handle_plan)

    # --- run ---
    run_parser = subparsers.add_parser(
        "run",
        help="Execute a manifest-driven workflow on the specified provider",
    )
    run_parser.add_argument(
        "manifest",
        nargs="?",
        default=settings.manifest_path,
        help="Path to scalable.yaml (default: SCALABLE_MANIFEST or ./scalable.yaml)",
    )
    run_parser.add_argument(
        "--target",
        default=None,
        help="Target name override (default: first target or SCALABLE_TARGET)",
    )
    run_parser.add_argument(
        "--workflow",
        default=None,
        help="Path to a Python workflow file to execute on the cluster",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan and estimate cost without executing",
    )
    run_parser.set_defaults(handler=_handle_run)

    # --- report ---
    report_parser = subparsers.add_parser(
        "report",
        help="Summarize telemetry for a completed or running session",
    )
    report_parser.add_argument(
        "--runs-dir",
        default=settings.runs_dir,
        help="Runs directory (default: SCALABLE_RUNS_DIR or ./.scalable/runs)",
    )
    report_parser.add_argument(
        "--run-id",
        default=None,
        help="Explicit run directory name (e.g. run-20260519T120000Z-...)",
    )
    report_parser.add_argument(
        "--latest",
        action="store_true",
        help="Select the most recent run in --runs-dir",
    )
    report_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    report_parser.add_argument(
        "--output",
        default=None,
        help="Optional output file path",
    )
    report_parser.set_defaults(handler=_handle_report)

    # --- init-component (Phase 4) ---
    init_parser = subparsers.add_parser(
        "init-component",
        help="Analyze a model directory and propose a component manifest block",
    )
    init_parser.add_argument(
        "path",
        help="Path to the model directory to analyze",
    )
    init_parser.add_argument(
        "--name",
        default=None,
        help="Component name (default: directory basename)",
    )
    init_parser.add_argument(
        "--output",
        default=None,
        help="Output file path (default: stdout)",
    )
    init_parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip LLM enhancement, use heuristics only",
    )
    init_parser.set_defaults(handler=_handle_init_component)

    # --- diagnose (Phase 4) ---
    diagnose_parser = subparsers.add_parser(
        "diagnose",
        help="Classify failures from run telemetry and suggest fixes",
    )
    diagnose_parser.add_argument(
        "--runs-dir",
        default=settings.runs_dir,
        help="Runs directory (default: SCALABLE_RUNS_DIR or ./.scalable/runs)",
    )
    diagnose_parser.add_argument(
        "--run-id",
        default=None,
        help="Explicit run directory name",
    )
    diagnose_parser.add_argument(
        "--latest",
        action="store_true",
        help="Select the most recent run",
    )
    diagnose_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    diagnose_parser.add_argument(
        "--output",
        default=None,
        help="Output file path",
    )
    diagnose_parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip LLM enhancement, use heuristics only",
    )
    diagnose_parser.set_defaults(handler=_handle_diagnose)

    # --- explain (Phase 4) ---
    explain_parser = subparsers.add_parser(
        "explain",
        help="Render a human-readable explanation of an execution plan",
    )
    explain_parser.add_argument(
        "plan",
        nargs="?",
        default="plan.json",
        help="Path to plan.json (default: ./plan.json)",
    )
    explain_parser.add_argument(
        "--runs-dir",
        default=settings.runs_dir,
        help="Runs directory for historical context",
    )
    explain_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    explain_parser.add_argument(
        "--output",
        default=None,
        help="Output file path",
    )
    explain_parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip LLM enhancement, use heuristics only",
    )
    explain_parser.set_defaults(handler=_handle_explain)

    # --- compose (Phase 4) ---
    compose_parser = subparsers.add_parser(
        "compose",
        help="Generate a workflow from a natural-language description",
    )
    compose_parser.add_argument(
        "description",
        help="Natural-language description of the workflow to generate",
    )
    compose_parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write generated files (default: print to stdout)",
    )
    compose_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    compose_parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip LLM enhancement, use heuristics only",
    )
    compose_parser.set_defaults(handler=_handle_compose)

    # --- migrate (Phase 4) ---
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Propose manifest migration changes for provider/schema upgrades",
    )
    migrate_parser.add_argument(
        "manifest",
        nargs="?",
        default=settings.manifest_path,
        help="Path to scalable.yaml to migrate",
    )
    migrate_parser.add_argument(
        "--to-provider",
        default=None,
        help="Target provider to migrate to (kubernetes, aws, gcp)",
    )
    migrate_parser.add_argument(
        "--to-version",
        default=None,
        help="Target schema version",
    )
    migrate_parser.add_argument(
        "--goal",
        default=None,
        help="Free-form migration goal description",
    )
    migrate_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    migrate_parser.add_argument(
        "--output",
        default=None,
        help="Output file path",
    )
    migrate_parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip LLM enhancement, use heuristics only",
    )
    migrate_parser.set_defaults(handler=_handle_migrate)

    # --- stubs for future phases ---
    for command, phase in _STUB_COMMANDS.items():
        stub_parser = subparsers.add_parser(command, help=f"Reserved command (planned for {phase})")
        stub_parser.set_defaults(handler=_make_stub_handler(command, phase))

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the ``scalable`` CLI and return a process-compatible exit code."""
    parser = _build_parser()
    args_list = sys.argv[1:] if argv is None else argv
    try:
        args = parser.parse_args(args_list)
    except SystemExit as exc:
        return int(exc.code)

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help(sys.stderr)
        return 2

    return int(handler(args))


if __name__ == "__main__":  # pragma: no cover - exercised via console script
    raise SystemExit(main(sys.argv[1:]))
