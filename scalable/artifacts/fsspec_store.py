"""Fsspec-based artifact store for remote backends (S3, GCS, memory, etc.)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .base import ArtifactKind, ArtifactRef


def _import_fsspec():
    """Import fsspec with a clear error message."""
    try:
        import fsspec

        return fsspec
    except ImportError as exc:
        raise ImportError(
            "fsspec is required for remote artifact stores. "
            "Install with: pip install scalable[cloud]"
        ) from exc


class FsspecArtifactStore:
    """Artifact store backed by any fsspec-compatible filesystem.

    Supports S3 (``s3://``), GCS (``gs://``), and ``memory://`` for tests.

    Parameters
    ----------
    uri : str
        Base URI for the store (e.g. ``s3://bucket/artifacts/``).
    storage_options : dict[str, Any] | None
        Keyword arguments passed to ``fsspec.filesystem()``.
    """

    def __init__(
        self,
        uri: str,
        *,
        storage_options: dict[str, Any] | None = None,
    ) -> None:
        fsspec = _import_fsspec()
        self._uri = uri.rstrip("/")
        self._storage_options = storage_options or {}
        # Parse protocol from URI
        self._protocol = fsspec.utils.get_protocol(uri)
        self._fs = fsspec.filesystem(self._protocol, **self._storage_options)

    @property
    def scheme(self) -> str:
        return self._protocol

    @property
    def base_uri(self) -> str:
        return self._uri

    def _remote_path(self, remote_key: str) -> str:
        """Build full remote path from key."""
        return f"{self._uri}/{remote_key}"

    def put(
        self,
        local_path: str,
        remote_key: str,
        *,
        kind: ArtifactKind | None = None,
    ) -> ArtifactRef:
        """Upload a local file or directory to the remote store."""
        src = Path(local_path)
        remote = self._remote_path(remote_key)

        if kind is None:
            kind = ArtifactKind.DIRECTORY if src.is_dir() else ArtifactKind.FILE

        if src.is_dir():
            self._fs.put(str(src), remote, recursive=True)
            size = sum(
                f.stat().st_size for f in src.rglob("*") if f.is_file()
            )
            digest = None
        else:
            self._fs.put(str(src), remote)
            size = src.stat().st_size
            digest = self._compute_local_digest(src)

        return ArtifactRef(
            uri=remote,
            kind=kind,
            digest=digest,
            size_bytes=size,
        )

    def get(self, remote_key: str, local_path: str) -> str:
        """Download a stored artifact to a local path."""
        remote = self._remote_path(remote_key)
        dest = Path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        if self._fs.isdir(remote):
            self._fs.get(remote, str(dest), recursive=True)
        else:
            self._fs.get(remote, str(dest))

        return str(dest)

    def exists(self, remote_key: str) -> bool:
        """Check if an artifact exists at the given key."""
        remote = self._remote_path(remote_key)
        return self._fs.exists(remote)

    def list_artifacts(self, prefix: str = "") -> list[str]:
        """List artifact keys under the given prefix."""
        search_path = self._remote_path(prefix) if prefix else self._uri
        try:
            entries = self._fs.ls(search_path, detail=False)
        except FileNotFoundError:
            return []
        # Strip base URI prefix to return relative keys
        base = self._uri + "/"
        results: list[str] = []
        for entry in sorted(entries):
            if entry.startswith(base):
                results.append(entry[len(base):])
            else:
                results.append(entry)
        return results

    @staticmethod
    def _compute_local_digest(path: Path) -> str:
        """Compute SHA-256 of a local file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()


__all__ = ["FsspecArtifactStore"]
