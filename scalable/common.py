"""Common module-level primitives for the :mod:`scalable` package.

This module centralizes:

* The library logger (with a :class:`logging.NullHandler` attached so the
  library never emits records by default — applications opt in via
  ``logging.basicConfig`` or their own configuration).
* A :class:`Settings` dataclass holding values that used to be free-floating
  module globals (``cachedir``, ``SEED``). The legacy module-level names are
  preserved for backwards compatibility and continue to read/write to the
  process-wide singleton in :data:`settings`.

Environment overrides
---------------------

* ``SCALABLE_CACHE_DIR`` — default cache directory (default: ``./cache``).
* ``SCALABLE_SEED``     — default xxhash seed (default: ``987654321``).
* ``SCALABLE_LOG_LEVEL``— if set (e.g. ``DEBUG``), the library *will* emit
  records at that level using a basic stderr handler. Useful for ad-hoc
  debugging without forcing applications to configure logging.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

__all__ = ["logger", "settings", "Settings", "SEED", "cachedir", "DEFAULT_SEED"]

DEFAULT_SEED: int = 987654321
DEFAULT_CACHE_DIR: str = "./cache"
DEFAULT_MANIFEST_PATH: str = "./scalable.yaml"
DEFAULT_RUNS_DIR: str = "./.scalable/runs"


@dataclass
class Settings:
    """Process-wide tunables for :mod:`scalable`.

    Attributes
    ----------
    cache_dir:
        Directory used by the disk cache backend in :mod:`scalable.caching`.
    seed:
        Seed for ``xxhash`` digests. Changing this invalidates every existing
        cache entry, so it should be treated as a one-time deployment choice.
    cache_remote_uri:
        Remote storage URI for the opt-in remote cache backend (Phase 3).
        Set via ``SCALABLE_CACHE_REMOTE`` env var. When ``None``, only local
        disk caching is used.
    default_storage:
        Default artifact/output storage URI override. Takes precedence over
        the ``project.default_storage`` manifest field.
    runs_dir_remote:
        Remote storage URI for persisting run telemetry. When set, telemetry
        is also synced to this remote location.
    """

    cache_dir: str = field(
        default_factory=lambda: os.environ.get("SCALABLE_CACHE_DIR", DEFAULT_CACHE_DIR)
    )
    seed: int = field(
        default_factory=lambda: int(os.environ.get("SCALABLE_SEED", DEFAULT_SEED))
    )
    manifest_path: str = field(
        default_factory=lambda: os.environ.get("SCALABLE_MANIFEST", DEFAULT_MANIFEST_PATH)
    )
    target: str | None = field(default_factory=lambda: os.environ.get("SCALABLE_TARGET"))
    runs_dir: str = field(
        default_factory=lambda: os.environ.get("SCALABLE_RUNS_DIR", DEFAULT_RUNS_DIR)
    )
    telemetry_enabled: bool = field(
        default_factory=lambda: bool(int(os.environ.get("SCALABLE_TELEMETRY", "1")))
    )
    telemetry_parquet: bool = field(
        default_factory=lambda: bool(int(os.environ.get("SCALABLE_TELEMETRY_PARQUET", "0")))
    )
    # Phase 3 additions
    cache_remote_uri: str | None = field(
        default_factory=lambda: os.environ.get("SCALABLE_CACHE_REMOTE")
    )
    default_storage: str | None = field(
        default_factory=lambda: os.environ.get("SCALABLE_DEFAULT_STORAGE")
    )
    runs_dir_remote: str | None = field(
        default_factory=lambda: os.environ.get("SCALABLE_RUNS_DIR_REMOTE")
    )


#: Process-wide settings singleton. Mutating attributes on this instance
#: changes behaviour for subsequent calls into the library.
settings: Settings = Settings()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger: logging.Logger = logging.getLogger("scalable")

# Library best practice: ship a NullHandler so we never emit records unless
# the consuming application configured logging.
if not any(isinstance(h, logging.NullHandler) for h in logger.handlers):
    logger.addHandler(logging.NullHandler())

_env_level = os.environ.get("SCALABLE_LOG_LEVEL")
if _env_level:
    # Opt-in: attach a basic stderr handler at the requested level.
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    logger.addHandler(_handler)
    try:
        logger.setLevel(_env_level.upper())
    except (TypeError, ValueError):  # pragma: no cover - defensive
        logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Backwards-compatible module-level aliases
# ---------------------------------------------------------------------------
# Older code paths import ``cachedir`` and ``SEED`` directly. We keep those
# names but back them with the singleton via module-level descriptors so any
# mutation goes through the dataclass.

def __getattr__(name: str) -> int | str:  # pragma: no cover - exercised via tests
    if name == "cachedir":
        return settings.cache_dir
    if name == "SEED":
        return settings.seed
    raise AttributeError(f"module 'scalable.common' has no attribute {name!r}")


# Provide concrete values too so ``from scalable.common import SEED`` works
# at import time (the ``__getattr__`` hook only fires for missing names).
SEED: int = settings.seed
cachedir: str = settings.cache_dir
