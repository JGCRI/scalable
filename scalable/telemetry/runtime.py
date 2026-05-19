"""Runtime telemetry context plumbing for session, client, and caching hooks."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .store import TelemetryStore


_ACTIVE_STORE: ContextVar[TelemetryStore | None] = ContextVar(
    "scalable_active_telemetry_store", default=None
)
_TASK_CONTEXT: ContextVar[dict[str, str | None] | None] = ContextVar(
    "scalable_task_context", default=None
)
_GLOBAL_ACTIVE_STORE: TelemetryStore | None = None


def set_active_store(store: TelemetryStore | None) -> Token[TelemetryStore | None]:
    """Set process-local active telemetry store and return its token."""
    global _GLOBAL_ACTIVE_STORE
    _GLOBAL_ACTIVE_STORE = store
    return _ACTIVE_STORE.set(store)


def reset_active_store(token: Token[TelemetryStore | None]) -> None:
    """Reset active telemetry store to previous value."""
    global _GLOBAL_ACTIVE_STORE
    _ACTIVE_STORE.reset(token)
    _GLOBAL_ACTIVE_STORE = _ACTIVE_STORE.get()


def get_active_store() -> TelemetryStore | None:
    """Return the currently active telemetry store, if any."""
    scoped = _ACTIVE_STORE.get()
    if scoped is not None:
        return scoped
    return _GLOBAL_ACTIVE_STORE


@contextmanager
def task_context(
    *,
    task_name: str | None,
    component: str | None,
    tag: str | None,
):
    """Temporarily bind task execution context for cache and artifact hooks."""
    token = _TASK_CONTEXT.set(
        {
            "task_name": task_name,
            "component": component,
            "tag": tag,
        }
    )
    try:
        yield
    finally:
        _TASK_CONTEXT.reset(token)


def get_task_context() -> dict[str, str | None] | None:
    """Get active task context for the current execution context."""
    value = _TASK_CONTEXT.get()
    if value is None:
        return None
    return dict(value)


def emit_cache_event(*, function_name: str, key_digest: str, hit: bool, duration_s: float) -> None:
    """Record a cache event through the active telemetry store, if configured."""
    store = get_active_store()
    if store is None:
        return

    context = get_task_context() or {}
    store.record_cache_event(
        function_name=function_name,
        key_digest=key_digest,
        hit=hit,
        duration_s=duration_s,
        task_name=context.get("task_name"),
        component=context.get("component"),
        tag=context.get("tag"),
    )


def emit_worker_event(*, provider: str, state: str, component: str | None = None, details: dict[str, Any] | None = None) -> None:
    """Record provider worker/cluster events via the active telemetry store."""
    store = get_active_store()
    if store is None:
        return
    store.record_worker_event(
        provider=provider,
        state=state,
        component=component,
        details=details or {},
    )


__all__ = [
    "emit_cache_event",
    "emit_worker_event",
    "get_active_store",
    "get_task_context",
    "reset_active_store",
    "set_active_store",
    "task_context",
]
