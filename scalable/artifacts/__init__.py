"""Artifact store abstraction layer.

Provides a protocol-based interface for storing and retrieving workflow
artifacts (outputs, intermediate files) across local and remote backends.
"""

from __future__ import annotations

from .base import ArtifactKind, ArtifactRef, ArtifactStore
from .factory import build_artifact_store
from .local import LocalArtifactStore

__all__ = [
    "ArtifactKind",
    "ArtifactRef",
    "ArtifactStore",
    "LocalArtifactStore",
    "build_artifact_store",
]
