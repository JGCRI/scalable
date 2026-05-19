"""Top-level ``ScalableSession`` user entry point (v2.0.0 Phase 1).

:class:`~scalable.session.session.ScalableSession` is the public face of
the v2.0.0 API surface advertised in the master plan
(``ScalableSession.from_yaml(...)``, ``session.plan(...)``,
``session.start(...)``). Phase 1 ships a minimal deterministic
implementation; Phases 2-5 layer telemetry, AI planning, and ML resource
advice onto the same surface without breaking the constructor signatures.
"""

from __future__ import annotations

__all__: list[str] = []
