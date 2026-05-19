"""Regression tests for top-level ``scalable`` public API exports."""

from __future__ import annotations


def test_top_level_exports_include_session_and_provider_symbols() -> None:
    import scalable

    exported = set(scalable.__all__)

    assert "ScalableSession" in exported
    assert "DeploymentProvider" in exported
    assert "LocalProvider" in exported
    assert "SlurmProvider" in exported


def test_legacy_exports_remain_available() -> None:
    import scalable

    exported = set(scalable.__all__)

    assert "JobQueueCluster" in exported
    assert "SlurmCluster" in exported
    assert "ScalableClient" in exported
    assert "SEED" in exported
    assert "settings" in exported

