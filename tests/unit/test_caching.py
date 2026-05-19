"""Unit tests for :mod:`scalable.caching`."""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scalable import caching
from scalable.caching import (
    DirType,
    FileType,
    ObjectType,
    UtilityType,
    ValueType,
    cacheable,
    convert_to_type,
)


@pytest.fixture(autouse=True)
def _isolated_cache_dir(tmp_path, monkeypatch):
    """Point the disk cache at a tmp dir and clear the per-process LRU."""
    monkeypatch.setattr(caching.settings, "cache_dir", str(tmp_path / "cache"))
    caching._shared_cache.cache_clear()
    # Reset path-sniffing warning latch so each test sees a fresh state.
    monkeypatch.setattr(caching, "_PATH_SNIFFING_WARNED", False)
    yield


# ---------------------------------------------------------------------------
# Type wrappers
# ---------------------------------------------------------------------------


def test_value_type_is_deterministic():
    assert hash(ValueType("hello")) == hash(ValueType("hello"))
    assert hash(ValueType(42)) == hash(ValueType(42))


def test_value_type_distinguishes_distinct_strings():
    assert hash(ValueType("a")) != hash(ValueType("b"))


def test_file_type_streams_large_file(tmp_path: Path):
    f = tmp_path / "big.bin"
    f.write_bytes(b"x" * (3 * 1024 * 1024 + 17))  # ~3 MB
    digest = hash(FileType(str(f)))
    # Recomputing yields the same digest (no rewinding bugs).
    assert hash(FileType(str(f))) == digest


def test_file_type_missing_raises(tmp_path: Path):
    with pytest.raises(ValueError):
        hash(FileType(str(tmp_path / "missing")))


def test_dir_type_recursive(tmp_path: Path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.txt").write_text("a")
    (sub / "b.txt").write_text("b")
    digest = hash(DirType(str(tmp_path)))
    # Mutating contents changes digest
    (sub / "c.txt").write_text("c")
    assert hash(DirType(str(tmp_path))) != digest


def test_object_type_swallows_only_typeerror():
    # Mixed key types should fall back to insertion order, not crash.
    d = {1: "a", "b": 2}
    h = hash(ObjectType(d))
    # Re-hashing same dict gives same digest
    assert hash(ObjectType({1: "a", "b": 2})) == h


def test_object_type_unpicklable_raises():
    class NotPicklable:
        def __reduce__(self):
            raise TypeError("nope")

    with pytest.raises(TypeError):
        hash(ObjectType(NotPicklable()))


def test_utility_type_array_dtype_matters():
    a = np.array([1, 2, 3], dtype=np.int32)
    b = np.array([1, 2, 3], dtype=np.int64)
    assert hash(UtilityType(a)) != hash(UtilityType(b))


def test_utility_type_dataframe():
    df = pd.DataFrame({"a": [1, 2, 3]})
    assert hash(UtilityType(df)) == hash(UtilityType(df.copy()))


# ---------------------------------------------------------------------------
# convert_to_type — deprecation behaviour for path sniffing
# ---------------------------------------------------------------------------


def test_convert_to_type_path_sniffing_warns_once(tmp_path: Path):
    f = tmp_path / "f.txt"
    f.write_text("hi")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        wrapped = convert_to_type(str(f))
        assert isinstance(wrapped, FileType)
        # Second call does not warn again
        wrapped_again = convert_to_type(str(f))
        assert isinstance(wrapped_again, FileType)

    deprecation = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert len(deprecation) == 1


def test_convert_to_type_disable_path_sniffing(tmp_path: Path, monkeypatch):
    f = tmp_path / "f.txt"
    f.write_text("hi")
    monkeypatch.setattr(caching, "PATH_SNIFFING_ENABLED", False)
    wrapped = convert_to_type(str(f))
    assert isinstance(wrapped, ValueType)


def test_convert_to_type_dispatches():
    assert isinstance(convert_to_type(1), ValueType)
    assert isinstance(convert_to_type(1.5), ValueType)
    assert isinstance(convert_to_type(b"abc"), ValueType)
    assert isinstance(convert_to_type([1, 2]), ObjectType)
    assert isinstance(convert_to_type({"k": "v"}), ObjectType)
    assert isinstance(convert_to_type(np.zeros(3)), UtilityType)


# ---------------------------------------------------------------------------
# cacheable decorator
# ---------------------------------------------------------------------------


def test_cacheable_returns_cached_value():
    calls = {"n": 0}

    @cacheable(return_type=ValueType, x=ValueType)
    def add_one(x):
        calls["n"] += 1
        return x + 1

    assert add_one(1) == 2
    assert add_one(1) == 2
    assert calls["n"] == 1


def test_cacheable_recompute_bypasses_cache():
    calls = {"n": 0}

    @cacheable(return_type=ValueType, recompute=True, x=ValueType)
    def add_one(x):
        calls["n"] += 1
        return x + 1

    add_one(1)
    add_one(1)
    assert calls["n"] == 2


def test_cacheable_void_passthrough():
    @cacheable(void=True)
    def side_effect(x):
        return x * 2

    # ``void=True`` means the decorator returns the original function;
    # nothing is cached.
    assert side_effect(3) == 6
    assert side_effect.__name__ == "side_effect"


def test_cacheable_works_on_lambdas_via_fingerprint_fallback():
    # Lambdas don't have source available in many contexts; ensure the
    # decorator still produces a stable cache key without crashing.
    f = cacheable(return_type=ValueType, x=ValueType)(lambda x: x * 10)
    assert f(2) == 20
    # Second call should hit the cache
    calls = {"n": 0}

    def counted(x):
        calls["n"] += 1
        return x * 10

    g = cacheable(return_type=ValueType, x=ValueType)(counted)
    g(2)
    g(2)
    assert calls["n"] == 1


def test_cacheable_no_args_form():
    @cacheable
    def double(x):
        return x * 2

    assert double(3) == 6


def test_cacheable_distinguishes_arguments():
    @cacheable(return_type=ValueType, x=ValueType)
    def add_one(x):
        return x + 1

    assert add_one(1) == 2
    assert add_one(2) == 3
