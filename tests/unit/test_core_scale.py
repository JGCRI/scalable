"""Unit tests for :mod:`scalable.core` — JobQueueCluster.scale / shutdown contract.

We test the ``scale`` and ``shutdown`` methods without instantiating the full
:class:`distributed.deploy.SpecCluster` (which would bind sockets and start an
event loop). Instead, we monkeypatch :meth:`SpecCluster.scale` to record
invocations.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def cluster_factory(monkeypatch):
    """Return a factory that builds an uninitialized JobQueueCluster + records.

    The returned tuple is ``(make_cluster, calls)`` where ``calls`` is a list
    populated with each forwarded ``SpecCluster.scale`` invocation.
    """
    from distributed.deploy.spec import SpecCluster

    from scalable.core import JobQueueCluster

    calls: list[dict] = []

    def fake_scale(self, n=None, jobs=0, memory=None, cores=None):
        calls.append({"n": n, "jobs": jobs, "memory": memory, "cores": cores})
        return None

    monkeypatch.setattr(SpecCluster, "scale", fake_scale)

    def make_cluster():
        # Build the instance without running ``__init__`` to avoid the rest
        # of the constructor side effects (port checks, scheduler bootstrap,
        # etc.). We're only exercising scale() / shutdown().
        c = JobQueueCluster.__new__(JobQueueCluster)
        c.exited = False
        return c

    return make_cluster, calls


def test_scale_no_longer_flips_exited_flag(cluster_factory):
    make_cluster, calls = cluster_factory
    c = make_cluster()
    assert c.exited is False
    c.scale(0)
    # Historic behaviour was: scale(0) silently flipped exited=True.
    assert c.exited is False
    assert calls == [{"n": 0, "jobs": 0, "memory": None, "cores": None}]


def test_scale_forwards_n_kwarg(cluster_factory):
    make_cluster, calls = cluster_factory
    c = make_cluster()
    c.scale(n=4)
    assert calls == [{"n": 4, "jobs": 0, "memory": None, "cores": None}]


def test_scale_with_none_does_not_set_exited(cluster_factory):
    make_cluster, calls = cluster_factory
    c = make_cluster()
    c.scale(n=None)
    assert c.exited is False
    assert calls == [{"n": None, "jobs": 0, "memory": None, "cores": None}]


def test_shutdown_flips_exited_and_scales_to_zero(cluster_factory):
    make_cluster, calls = cluster_factory
    c = make_cluster()
    c.shutdown()
    assert c.exited is True
    assert calls == [{"n": 0, "jobs": 0, "memory": None, "cores": None}]
