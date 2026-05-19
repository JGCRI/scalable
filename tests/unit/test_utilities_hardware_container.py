"""Unit tests for :mod:`scalable.utilities` — HardwareResources and Container."""

from __future__ import annotations

import threading
import warnings

import pytest

from scalable.utilities import (
    Container,
    HardwareResources,
    _parse_memory_to_gb,
)

# ---------------------------------------------------------------------------
# _parse_memory_to_gb
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        ("8G", 8),
        ("8GB", 8),
        ("2G", 2),
        ("500MB", 1),  # was 0 in the legacy floor-divide implementation
        ("1500MB", 2),  # ceiling-divide
        (10**9, 1),
        (0, 0),
        (None, 0),
        ("", 0),
    ],
)
def test_parse_memory_to_gb(value, expected):
    assert _parse_memory_to_gb(value) == expected


def test_parse_memory_to_gb_default():
    assert _parse_memory_to_gb(None, default=42) == 42


# ---------------------------------------------------------------------------
# HardwareResources — basic semantics
# ---------------------------------------------------------------------------


def make_ledger(min_cpus=0, min_memory=0):
    """Return a fresh ledger with relaxed minimums for unit testing."""
    return HardwareResources(min_cpus=min_cpus, min_memory=min_memory)


def test_assign_resources_records_node():
    h = make_ledger()
    assert h.assign_resources("node-a", cpus=8, memory=16, jobid="J1") is True
    assert "node-a" in h.nodes
    assert h.assigned["node-a"] == {"cpus": 8, "memory": 16, "jobid": "J1"}
    assert h.available["node-a"] == {"cpus": 8, "memory": 16, "jobid": "J1"}
    assert "J1" in h.active


def test_assign_resources_idempotent_returns_false():
    h = make_ledger()
    assert h.assign_resources("node-a", 8, 16, "J1") is True
    assert h.assign_resources("node-a", 8, 16, "J1") is False


def test_get_node_jobid_unknown_raises():
    h = make_ledger()
    with pytest.raises(ValueError):
        h.get_node_jobid("ghost")


def test_utilize_and_release_round_trip():
    h = make_ledger()
    h.assign_resources("node-a", cpus=10, memory=20, jobid="J1")
    h.utilize_resources("node-a", cpus=4, memory=8, jobid="J1")
    assert h.available["node-a"] == {"cpus": 6, "memory": 12, "jobid": "J1"}
    assert "node-a" in h.active["J1"]
    assert h.has_active_nodes("J1") is True

    h.release_resources("node-a", cpus=4, memory=8, jobid="J1")
    assert h.available["node-a"]["cpus"] == 10
    assert h.has_active_nodes("J1") is False


def test_utilize_resources_rejects_overcommit():
    h = make_ledger(min_cpus=2, min_memory=2)
    h.assign_resources("node-a", cpus=4, memory=4, jobid="J1")
    with pytest.raises(ValueError):
        h.utilize_resources("node-a", cpus=4, memory=4, jobid="J1")


def test_utilize_resources_rejects_wrong_jobid():
    h = make_ledger()
    h.assign_resources("node-a", cpus=4, memory=4, jobid="J1")
    with pytest.raises(ValueError):
        h.utilize_resources("node-a", cpus=1, memory=1, jobid="OTHER")


def test_get_available_node_returns_first_fit():
    h = make_ledger(min_cpus=0, min_memory=0)
    h.assign_resources("node-a", cpus=2, memory=2, jobid="J1")
    h.assign_resources("node-b", cpus=8, memory=16, jobid="J1")
    node = h.get_available_node(cpus=4, memory=8)
    assert node == "node-b"


def test_get_available_node_returns_none():
    h = make_ledger(min_cpus=0, min_memory=0)
    h.assign_resources("node-a", cpus=2, memory=2, jobid="J1")
    assert h.get_available_node(cpus=99, memory=99) is None


def test_remove_jobid_nodes_clears_state():
    h = make_ledger()
    h.assign_resources("node-a", 8, 16, "J1")
    h.assign_resources("node-b", 8, 16, "J1")
    h.assign_resources("node-c", 8, 16, "J2")

    h.remove_jobid_nodes("J1")

    assert h.nodes == ["node-c"]
    assert "J1" not in h.active
    assert "node-a" not in h.assigned
    assert "node-b" not in h.assigned
    assert "node-c" in h.assigned


def test_is_assigned_is_o1():
    h = make_ledger()
    h.assign_resources("node-a", 8, 16, "J1")
    assert h.is_assigned("J1") is True
    assert h.is_assigned("missing") is False


# ---------------------------------------------------------------------------
# HardwareResources — concurrency
# ---------------------------------------------------------------------------


def test_concurrent_assign_does_not_corrupt_state():
    """Many threads racing on assign should produce a self-consistent ledger."""
    h = make_ledger()
    n_threads = 16
    n_per_thread = 50

    def worker(tid):
        for j in range(n_per_thread):
            node = f"t{tid}-n{j}"
            h.assign_resources(node, cpus=4, memory=4, jobid=f"J{tid}")

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Every (tid, j) pair must be assigned exactly once.
    expected = {f"t{t}-n{j}" for t in range(n_threads) for j in range(n_per_thread)}
    assert set(h.nodes) == expected
    # No duplicate entries in nodes list.
    assert len(h.nodes) == len(expected)
    # active dict tracks every job we created.
    assert set(h.active) == {f"J{t}" for t in range(n_threads)}


# ---------------------------------------------------------------------------
# HardwareResources — legacy global setters emit DeprecationWarning
# ---------------------------------------------------------------------------


def test_set_min_free_cpus_deprecated():
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        with pytest.raises(DeprecationWarning):
            HardwareResources.set_min_free_cpus(5)
    # Reset to default for downstream tests
    HardwareResources.MIN_CPUS = 10


def test_set_min_free_memory_deprecated():
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        with pytest.raises(DeprecationWarning):
            HardwareResources.set_min_free_memory(5)
    HardwareResources.MIN_MEMORY = 20


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


def make_spec(memory="8G", path="/tmp/c.sif", dirs=None, preload=None, cpus=4):
    return {
        "CPUs": cpus,
        "Memory": memory,
        "Path": path,
        "Dirs": dirs,
        "PreloadScript": preload,
    }


def test_container_normalizes_dirs_with_scratch_default():
    c = Container("gcam", make_spec(dirs={"/host": "/cont"}))
    assert c.directories["/scratch"] == "/tmp"
    assert c.directories["/host"] == "/cont"
    # Memory parsed to whole GB
    assert c.memory == 8


def test_container_500mb_does_not_truncate_to_zero():
    c = Container("small", make_spec(memory="500MB"))
    assert c.memory == 1


def test_container_per_instance_runtimes_independent():
    a = Container("a", make_spec(), runtime="apptainer")
    d = Container("d", make_spec(), runtime="docker")
    assert a.get_runtime() == "apptainer"
    assert a.get_runtime_directive() == "exec"
    assert d.get_runtime() == "docker"
    assert d.get_runtime_directive() == "run"


def test_container_unknown_runtime_raises():
    c = Container("x", make_spec(), runtime="podman")
    with pytest.raises(ValueError):
        c.get_runtime_directive()


def test_container_register_runtime_directive_picked_up_by_new_instances():
    Container.register_runtime_directive("podman", "run")
    try:
        c = Container("x", make_spec(), runtime="podman")
        assert c.get_runtime_directive() == "run"
    finally:
        Container._runtime_directives.pop("podman", None)


def test_container_static_set_runtime_deprecated():
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        with pytest.raises(DeprecationWarning):
            Container.set_runtime("apptainer")
    # Reset to safe default
    Container._runtime = "apptainer"


def test_container_get_command_includes_binds_and_runtime():
    c = Container(
        "demo",
        make_spec(memory="2G", path="/img.sif", dirs={"/host": "/c"}),
        runtime="apptainer",
    )
    cmd = c.get_command(env_vars={"FOO": "bar"})
    assert cmd[0] == "apptainer"
    assert cmd[1] == "exec"
    # env var present
    assert "--env" in cmd and "FOO=bar" in cmd
    # explicit bind from caller present
    assert "/host:/c" in cmd
    # default scratch bind present
    assert "/scratch:/tmp" in cmd
    # path is the last positional argument
    assert cmd[-1] == "/img.sif"


def test_container_dirs_alias_safe_between_instances():
    spec = make_spec(dirs={"/host": "/cont"})
    a = Container("a", spec)
    # Mutating ``a.directories`` must not leak into a fresh Container from a
    # *different* spec_dict.
    a.directories["/extra"] = "/extra-c"
    b = Container("b", make_spec(dirs={"/other": "/o"}))
    assert "/extra" not in b.directories
