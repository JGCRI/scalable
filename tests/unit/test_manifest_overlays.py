"""Unit tests for scalable.manifest.overlays module."""

from __future__ import annotations

import pytest

from scalable.manifest.errors import ManifestSchemaError
from scalable.manifest.overlays import deep_merge, resolve_overlay


class TestDeepMerge:
    def test_basic_merge(self):
        base = {"a": 1, "b": 2}
        overlay = {"b": 3, "c": 4}
        result = deep_merge(base, overlay)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_dict_merge(self):
        base = {"top": {"a": 1, "b": 2}}
        overlay = {"top": {"b": 3, "c": 4}}
        result = deep_merge(base, overlay)
        assert result == {"top": {"a": 1, "b": 3, "c": 4}}

    def test_list_replacement(self):
        base = {"items": [1, 2, 3]}
        overlay = {"items": [4, 5]}
        result = deep_merge(base, overlay)
        assert result == {"items": [4, 5]}

    def test_no_mutation(self):
        base = {"a": {"nested": 1}}
        overlay = {"a": {"nested": 2}}
        result = deep_merge(base, overlay)
        assert base["a"]["nested"] == 1
        assert result["a"]["nested"] == 2

    def test_empty_overlay(self):
        base = {"a": 1}
        result = deep_merge(base, {})
        assert result == {"a": 1}

    def test_deeply_nested(self):
        base = {"l1": {"l2": {"l3": {"val": "original"}}}}
        overlay = {"l1": {"l2": {"l3": {"val": "modified", "new": True}}}}
        result = deep_merge(base, overlay)
        assert result["l1"]["l2"]["l3"] == {"val": "modified", "new": True}


class TestResolveOverlay:
    def test_no_overlay_applied(self):
        doc = {
            "version": 1,
            "project": {"name": "test"},
            "targets": {"local": {"provider": "local"}},
        }
        resolved, unresolved = resolve_overlay(doc)
        assert resolved == doc
        assert unresolved is None

    def test_overlay_from_target(self):
        doc = {
            "version": 1,
            "project": {"name": "test"},
            "targets": {
                "prod": {"provider": "kubernetes", "overlay": "k8s-prod"},
            },
            "overlays": {
                "k8s-prod": {
                    "targets": {
                        "prod": {"namespace": "production"},
                    },
                },
            },
        }
        resolved, unresolved = resolve_overlay(doc, target_name="prod")
        assert "overlays" not in resolved
        assert resolved["targets"]["prod"]["namespace"] == "production"
        assert unresolved is not None
        assert "overlays" not in unresolved

    def test_explicit_overlay_name(self):
        doc = {
            "version": 1,
            "project": {"name": "test"},
            "targets": {"dev": {"provider": "local"}},
            "overlays": {
                "extra-memory": {
                    "components": {"model": {"memory": "32G"}},
                },
            },
            "components": {"model": {"cpus": 4, "memory": "8G"}},
        }
        resolved, unresolved = resolve_overlay(doc, overlay_name="extra-memory")
        assert resolved["components"]["model"]["memory"] == "32G"
        assert resolved["components"]["model"]["cpus"] == 4

    def test_unknown_overlay_raises(self):
        doc = {
            "version": 1,
            "project": {"name": "test"},
            "targets": {"gke": {"provider": "kubernetes", "overlay": "missing"}},
            "overlays": {},
        }
        with pytest.raises(ManifestSchemaError, match="missing"):
            resolve_overlay(doc, target_name="gke")

    def test_overlay_strips_overlay_ref_from_target(self):
        doc = {
            "version": 1,
            "project": {"name": "test"},
            "targets": {"prod": {"provider": "kubernetes", "overlay": "prod-cfg"}},
            "overlays": {
                "prod-cfg": {"targets": {"prod": {"namespace": "prod"}}},
            },
        }
        resolved, _ = resolve_overlay(doc, target_name="prod")
        # The resolved target should not have the 'overlay' key
        assert "overlay" not in resolved["targets"]["prod"]


class TestParserOverlayIntegration:
    """Test that parse_manifest correctly passes through overlay resolution."""

    def test_parse_with_overlay(self):
        from scalable.manifest.parser import parse_manifest

        doc = {
            "version": 1,
            "project": {"name": "test"},
            "targets": {"gke": {"provider": "kubernetes", "overlay": "gke-prod"}},
            "components": {"model": {"cpus": 2, "memory": "4G"}},
            "tasks": {"run_model": {"component": "model"}},
            "overlays": {
                "gke-prod": {
                    "components": {"model": {"memory": "16G"}},
                },
            },
        }
        manifest = parse_manifest(doc, target_name="gke")
        # Overlay should have changed memory
        assert manifest.components["model"].memory == "16G"
        assert manifest.components["model"].cpus == 2
        # raw_unresolved should exist
        assert manifest.raw_unresolved is not None

    def test_parse_without_overlay(self):
        from scalable.manifest.parser import parse_manifest

        doc = {
            "version": 1,
            "project": {"name": "test"},
            "targets": {"local": {"provider": "local"}},
            "components": {"model": {"cpus": 2}},
            "tasks": {"run_model": {"component": "model"}},
        }
        manifest = parse_manifest(doc)
        assert manifest.raw_unresolved is None
        assert manifest.components["model"].cpus == 2
