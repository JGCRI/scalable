"""``scalable`` console-script CLI (v2.0.0 Phase 1).

Phase 1 implements two subcommands -- ``scalable validate`` and
``scalable plan --dry-run`` -- both of which operate purely on a manifest
plus provider abstractions and never instantiate a scheduler.

The remaining subcommand namespace (``run``, ``diagnose``, ``explain``,
``init-component``, ``compose``, ``report``) is registered as Phase 1 stubs
that print a phase-pointer message on invocation. This locks the UX
namespace early so third-party CLIs don't collide with future Scalable
verbs and so Phases 2-5 only fill behaviour rather than surface.
"""

from __future__ import annotations

__all__: list[str] = []
