"""``scalable`` console-script CLI (v2.0.0 Phase 2).

Implemented subcommands:

* ``scalable validate``
* ``scalable plan --dry-run``
* ``scalable report``

The remaining subcommand namespace (``run``, ``diagnose``, ``explain``,
``init-component``, ``compose``) is registered as explicit stubs
that print a phase-pointer message on invocation. This locks the UX
namespace early so third-party CLIs don't collide with future Scalable
verbs and so Phases 2-5 only fill behaviour rather than surface.
"""

from __future__ import annotations

__all__: list[str] = []
