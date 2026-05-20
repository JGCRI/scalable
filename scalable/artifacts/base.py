"""ArtifactStore protocol and supporting types."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


class ArtifactKind(enum.StrEnum):
    """Classification of artifact content type."""

    FILE = "file"
    DIRECTORY = "dir"
    BLOB = "blob"


@dataclass(frozen=True)
class ArtifactRef:
    """Reference to a stored artifact.

    Attributes
    ----------
    uri : str
        Fully-qualified storage URI (e.g. ``file:///..``, ``s3://...``).
    kind : ArtifactKind
        Type of artifact stored.
    digest : str | None
        Content hash (SHA-256) if available.
    size_bytes : int | None
        Size in bytes if known.
    metadata : dict[str, Any]
        Provider-specific metadata.
    """

    uri: str
    kind: ArtifactKind
    digest: str | None = None
    size_bytes: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ArtifactStore(Protocol):
    """Protocol for artifact storage backends.

    All implementations must support ``put``, ``get``, ``exists``, and
    ``list_artifacts``. Remote implementations (S3, GCS) are gated behind
    the ``cloud`` extra.
    """

    @property
    def scheme(self) -> str:
        """URI scheme this store handles (e.g. ``"file"``, ``"s3"``)."""
        ...

    def put(self, local_path: str, remote_key: str, *, kind: ArtifactKind | None = None) -> ArtifactRef:
        """Upload/copy a local file or directory to the store.

        Parameters
        ----------
        local_path : str
            Path to the local file or directory to store.
        remote_key : str
            Logical key (relative path) under the store root.
        kind : ArtifactKind | None
            Override artifact kind detection.

        Returns
        -------
        ArtifactRef
            Reference to the stored artifact.
        """
        ...

    def get(self, remote_key: str, local_path: str) -> str:
        """Download/copy a stored artifact to a local path.

        Returns the local filesystem path where the artifact was placed.
        """
        ...

    def exists(self, remote_key: str) -> bool:
        """Check whether an artifact exists at the given key."""
        ...

    def list_artifacts(self, prefix: str = "") -> list[str]:
        """List artifact keys under the given prefix."""
        ...


__all__ = ["ArtifactKind", "ArtifactRef", "ArtifactStore"]
