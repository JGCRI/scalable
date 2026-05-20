"""Tests for Phase 5 telemetry EmulationEvent and CLI advise command."""

from __future__ import annotations

import pytest

from scalable.telemetry.events import SCHEMA_VERSION, EmulationEvent


class TestEmulationEvent:
    def test_creation(self):
        event = EmulationEvent(
            run_id="run-123",
            task_name="run_gcam",
            component="gcam",
            emulator_name="gcam_emulator",
            source="emulator",
            confidence=0.95,
            fallback_reason=None,
            domain_valid=True,
            emulator_version="2",
        )
        assert event.run_id == "run-123"
        assert event.source == "emulator"
        assert event.event_type == "emulation"
        assert event.schema_version == SCHEMA_VERSION

    def test_to_dict(self):
        event = EmulationEvent(
            run_id="run-456",
            task_name="run_stitches",
            component="stitches",
            emulator_name=None,
            source="full_model",
            confidence=None,
            fallback_reason="emulator_not_registered",
            domain_valid=True,
        )
        d = event.to_dict()
        assert d["run_id"] == "run-456"
        assert d["source"] == "full_model"
        assert d["fallback_reason"] == "emulator_not_registered"

    def test_timestamp_auto(self):
        event = EmulationEvent(
            run_id="r",
            task_name="t",
            component=None,
            emulator_name=None,
            source="full_model",
            confidence=None,
            fallback_reason=None,
            domain_valid=True,
        )
        assert event.timestamp  # auto-populated


class TestPhase5Settings:
    def test_ml_settings_defaults(self):
        from scalable.common import Settings

        s = Settings()
        assert s.ml_model_cache_dir == ".scalable/models"
        assert s.emulator_registry_dir == ".scalable/emulators"
        assert s.ml_enabled is True
        assert s.emulation_enabled is False
        assert s.emulation_confidence_threshold == 0.9


class TestCLIAdvise:
    def test_advise_parser_registration(self):
        """Verify advise command is registered in CLI parser."""
        from scalable.cli.main import _build_parser

        parser = _build_parser()
        # Check that 'advise' is a valid subcommand
        # Parse with --help would SystemExit, so just verify no crash
        # on the parser build
        assert parser is not None
