"""Unit tests for scalable.artifacts module."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from scalable.artifacts.base import ArtifactKind, ArtifactRef, ArtifactStore
from scalable.artifacts.factory import build_artifact_store
from scalable.artifacts.local import LocalArtifactStore


class TestArtifactKind:
    def test_enum_values(self):
        assert ArtifactKind.FILE == "file"
        assert ArtifactKind.DIRECTORY == "dir"
        assert ArtifactKind.BLOB == "blob"


class TestArtifactRef:
    def test_basic_creation(self):
        ref = ArtifactRef(
            uri="file:///tmp/test.txt",
            kind=ArtifactKind.FILE,
            digest="abc123",
            size_bytes=100,
        )
        assert ref.uri == "file:///tmp/test.txt"
        assert ref.kind == ArtifactKind.FILE
        assert ref.digest == "abc123"
        assert ref.size_bytes == 100
        assert ref.metadata == {}


class TestLocalArtifactStore:
    def test_protocol_conformance(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalArtifactStore(root=tmp)
            assert isinstance(store, ArtifactStore)

    def test_scheme(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalArtifactStore(root=tmp)
            assert store.scheme == "file"

    def test_put_and_get_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalArtifactStore(root=os.path.join(tmp, "store"))
            # Create a source file
            src_file = os.path.join(tmp, "source.txt")
            with open(src_file, "w") as f:
                f.write("hello world")

            ref = store.put(src_file, "data/output.txt")
            assert ref.kind == ArtifactKind.FILE
            assert ref.size_bytes == 11
            assert ref.digest is not None

            # Get it back
            dest = os.path.join(tmp, "retrieved.txt")
            result = store.get("data/output.txt", dest)
            assert Path(result).read_text() == "hello world"

    def test_put_and_get_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalArtifactStore(root=os.path.join(tmp, "store"))
            # Create a source directory
            src_dir = os.path.join(tmp, "srcdir")
            os.makedirs(src_dir)
            with open(os.path.join(src_dir, "a.txt"), "w") as f:
                f.write("aaa")
            with open(os.path.join(src_dir, "b.txt"), "w") as f:
                f.write("bbb")

            ref = store.put(src_dir, "outputs/batch1")
            assert ref.kind == ArtifactKind.DIRECTORY
            assert ref.size_bytes == 6  # 3+3

            # Get it back
            dest = os.path.join(tmp, "got_dir")
            store.get("outputs/batch1", dest)
            assert Path(os.path.join(dest, "a.txt")).read_text() == "aaa"
            assert Path(os.path.join(dest, "b.txt")).read_text() == "bbb"

    def test_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalArtifactStore(root=tmp)
            assert not store.exists("nope.txt")

            src = os.path.join(tmp, "src.txt")
            with open(src, "w") as f:
                f.write("x")
            store.put(src, "yes.txt")
            assert store.exists("yes.txt")

    def test_list_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            store_root = os.path.join(tmp, "store")
            store = LocalArtifactStore(root=store_root)

            src = os.path.join(tmp, "src.txt")
            with open(src, "w") as f:
                f.write("x")
            store.put(src, "a/1.txt")
            store.put(src, "a/2.txt")
            store.put(src, "b/3.txt")

            all_artifacts = store.list_artifacts()
            assert len(all_artifacts) == 3
            a_artifacts = store.list_artifacts("a")
            assert len(a_artifacts) == 2

    def test_get_missing_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalArtifactStore(root=tmp)
            with pytest.raises(FileNotFoundError):
                store.get("missing.txt", "/tmp/dest.txt")


class TestBuildArtifactStore:
    def test_local_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = build_artifact_store(tmp)
            assert isinstance(store, LocalArtifactStore)

    def test_file_uri(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = build_artifact_store(f"file://{tmp}")
            assert isinstance(store, LocalArtifactStore)

    def test_relative_path(self):
        store = build_artifact_store("./test_artifacts")
        assert isinstance(store, LocalArtifactStore)
        # Clean up
        import shutil

        shutil.rmtree("./test_artifacts", ignore_errors=True)
