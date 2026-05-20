"""Remote cache backend using the artifact store layer.

This module provides :class:`RemoteCacheBackend` which can be wired into
:mod:`scalable.caching` to store/retrieve cached results from remote
storage (S3, GCS) via the artifact store abstraction.

The remote cache is opt-in, controlled by the ``SCALABLE_CACHE_REMOTE``
environment variable or ``settings.cache_remote_uri``.
"""

from __future__ import annotations

import os
import pickle
import tempfile
from typing import Any

from scalable.common import logger


class RemoteCacheBackend:
    """Remote cache backend using artifact store for persistence.

    Parameters
    ----------
    uri : str
        Remote storage URI (e.g. ``s3://bucket/cache/``).
    """

    def __init__(self, uri: str) -> None:
        from .factory import build_artifact_store

        self._uri = uri
        self._store = build_artifact_store(uri)

    @property
    def uri(self) -> str:
        return self._uri

    def _cache_key(self, digest: str) -> str:
        """Build a remote key from a cache digest."""
        return f"cache/{digest[:2]}/{digest}"

    def get(self, digest: str) -> Any | None:
        """Attempt to retrieve a cached result by digest.

        Returns None if the key doesn't exist remotely.
        """
        key = self._cache_key(digest)
        if not self._store.exists(key):
            return None

        try:
            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
                tmp_path = tmp.name

            self._store.get(key, tmp_path)
            with open(tmp_path, "rb") as f:
                return pickle.load(f)
        except Exception as exc:
            logger.debug("remote cache get failed for %s: %s", digest, exc)
            return None
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def put(self, digest: str, value: Any) -> bool:
        """Store a value in the remote cache.

        Returns True on success, False on failure.
        """
        key = self._cache_key(digest)
        try:
            with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as tmp:
                tmp_path = tmp.name
                pickle.dump(value, tmp)

            from .base import ArtifactKind

            self._store.put(tmp_path, key, kind=ArtifactKind.BLOB)
            return True
        except Exception as exc:
            logger.debug("remote cache put failed for %s: %s", digest, exc)
            return False
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def exists(self, digest: str) -> bool:
        """Check if a digest exists in remote cache."""
        return self._store.exists(self._cache_key(digest))


def get_remote_cache_backend() -> RemoteCacheBackend | None:
    """Get the remote cache backend if configured.

    Checks ``SCALABLE_CACHE_REMOTE`` environment variable first, then
    falls back to ``settings.cache_remote_uri``.
    """
    from scalable.common import settings

    uri = os.environ.get("SCALABLE_CACHE_REMOTE") or getattr(
        settings, "cache_remote_uri", None
    )
    if not uri:
        return None

    try:
        return RemoteCacheBackend(uri)
    except Exception as exc:
        logger.warning("failed to initialize remote cache backend: %s", exc)
        return None


__all__ = ["RemoteCacheBackend", "get_remote_cache_backend"]
