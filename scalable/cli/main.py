"""``scalable`` console entry-point dispatcher.

Phase 1 ships two implemented subcommands:

* ``scalable validate``
* ``scalable plan --dry-run``

The namespace for later-phase verbs (``run``, ``diagnose``, ``explain``,
``init-component``, ``compose``, ``report``) is reserved as explicit stubs.
"""

from __future__ import annotations

import argparse
import sys

from scalable.common import settings

from .cmd_plan import run_plan
from .cmd_validate import run_validate

_STUB_COMMANDS: dict[str, str] = {
    "run": "Phase 2+",
    "diagnose": "Phase 4",
    "explain": "Phase 4",
    "init-component": "Phase 4",
    "compose": "Phase 4",
    "report": "Phase 2",
}


def _handle_validate(args: argparse.Namespace) -> int:
    return run_validate(args.manifest, target=args.target)


def _handle_plan(args: argparse.Namespace) -> int:
    return run_plan(
        args.manifest,
        target=args.target,
        dry_run=bool(args.dry_run),
        output=args.output,
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
