"""Factory for building artifact stores from URI strings."""

from __future__ import annotations

from .base import ArtifactStore
from .local import LocalArtifactStore


def build_artifact_store(uri: str) -> ArtifactStore:
    """Build an :class:`ArtifactStore` from a URI string.

    Parameters
    ----------
    uri : str
        Storage URI. Supported schemes:
        - ``file:///path`` or plain path — :class:`LocalArtifactStore`
        - ``s3://bucket/prefix`` — :class:`FsspecArtifactStore`
        - ``gs://bucket/prefix`` — :class:`FsspecArtifactStore`
        - ``memory://...`` — :class:`FsspecArtifactStore` (testing)

    Returns
    -------
    ArtifactStore
        An initialized artifact store instance.
    """
    if uri.startswith("file://"):
        path = uri[len("file://"):]
        return LocalArtifactStore(root=path)

    if uri.startswith("/") or uri.startswith("./") or uri.startswith(".."):
        return LocalArtifactStore(root=uri)

    # Remote stores require fsspec
    from .fsspec_store import FsspecArtifactStore

    return FsspecArtifactStore(uri)


__all__ = ["build_artifact_store"]
