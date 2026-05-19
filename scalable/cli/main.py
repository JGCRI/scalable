"""``scalable`` console entry-point dispatcher.

Phase 1 stub. The real subcommand wiring lands in WU-10
(``scalable validate`` and ``scalable plan --dry-run``); the remaining
subcommands (``run``, ``diagnose``, ``explain``, ``init-component``,
``compose``, ``report``) print a phase-pointer message until later phases
implement them.

This module exists in WU-1 only so the ``scalable = "scalable.cli.main:main"``
console script registered in ``pyproject.toml`` resolves at install time.
"""

from __future__ import annotations

import sys

_PHASE1_NOT_IMPLEMENTED_MESSAGE = (
    "scalable CLI: Phase 1 scaffolding only. "
    "Subcommands `validate` and `plan --dry-run` arrive in work-unit 10. "
    "See plans/v2.0.0_phase1_plan.md."
)


def main(argv: list[str] | None = None) -> int:
    """Entry-point referenced by ``[project.scripts] scalable = ...``.

    Phase 1 placeholder: prints a clear "not yet wired up" message and
    exits with status code 2 (matches argparse's convention for usage
    errors) so downstream automation that introspects the exit code knows
    to wait for WU-10.

    Parameters
    ----------
    argv : list of str, optional
        Argument vector excluding the program name. Defaults to
        ``sys.argv[1:]``. Accepted for testability and to match the final
        signature that WU-10 will deliver.

    Returns
    -------
    int
        Process exit code. Always ``2`` until WU-10 lands.
    """
    del argv  # unused in the WU-1 stub
    print(_PHASE1_NOT_IMPLEMENTED_MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover - exercised via console script
    raise SystemExit(main(sys.argv[1:]))
