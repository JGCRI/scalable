"""Local filesystem artifact store implementation."""

from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

from .base import ArtifactKind, ArtifactRef


class LocalArtifactStore:
    """Store artifacts on the local filesystem.

    Parameters
    ----------
    root : str | Path
        Root directory for artifact storage.
    """

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def scheme(self) -> str:
        return "file"

    @property
    def root(self) -> Path:
        return self._root

    def put(
        self,
        local_path: str,
        remote_key: str,
        *,
        kind: ArtifactKind | None = None,
    ) -> ArtifactRef:
        """Copy a local file or directory into the store."""
        src = Path(local_path)
        dest = self._root / remote_key

        if kind is None:
            kind = ArtifactKind.DIRECTORY if src.is_dir() else ArtifactKind.FILE

        dest.parent.mkdir(parents=True, exist_ok=True)

        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
        else:
            shutil.copy2(src, dest)
            size = dest.stat().st_size

        digest = self._compute_digest(dest) if not src.is_dir() else None
        uri = dest.resolve().as_uri()

        return ArtifactRef(
            uri=uri,
            kind=kind,
            digest=digest,
            size_bytes=size,
        )

    def get(self, remote_key: str, local_path: str) -> str:
        """Copy a stored artifact to a local destination."""
        src = self._root / remote_key
        dest = Path(local_path)

        if not src.exists():
            raise FileNotFoundError(f"artifact not found: {remote_key}")

        dest.parent.mkdir(parents=True, exist_ok=True)

        if src.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)

        return str(dest)

    def exists(self, remote_key: str) -> bool:
        """Check if an artifact exists."""
        return (self._root / remote_key).exists()

    def list_artifacts(self, prefix: str = "") -> list[str]:
        """List artifact keys under the given prefix."""
        search_root = self._root / prefix if prefix else self._root
        if not search_root.exists():
            return []
        results: list[str] = []
        for item in sorted(search_root.rglob("*")):
            if item.is_file():
                results.append(str(item.relative_to(self._root)))
        return results

    @staticmethod
    def _compute_digest(path: Path) -> str:
        """Compute SHA-256 digest of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()


__all__ = ["LocalArtifactStore"]
