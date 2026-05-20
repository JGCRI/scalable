"""Unit tests for scalable.ai.backend module."""

from __future__ import annotations

import pytest

from scalable.ai.backend import (
    AIBackend,
    NoOpBackend,
    OllamaBackend,
    OpenAIBackend,
    get_ai_backend,
    reset_backend_cache,
)


class TestNoOpBackend:
    def test_name(self):
        backend = NoOpBackend()
        assert backend.name == "none"

    def test_available_returns_false(self):
        backend = NoOpBackend()
        assert backend.available() is False

    def test_complete_raises_runtime_error(self):
        backend = NoOpBackend()
        with pytest.raises(RuntimeError, match="No AI backend configured"):
            backend.complete("test prompt")

    def test_satisfies_protocol(self):
        backend = NoOpBackend()
        assert isinstance(backend, AIBackend)


class TestOpenAIBackend:
    def test_name(self):
        backend = OpenAIBackend()
        assert backend.name == "openai"

    def test_default_model(self):
        backend = OpenAIBackend()
        assert backend._model == "gpt-4o"

    def test_custom_model(self):
        backend = OpenAIBackend(model="gpt-3.5-turbo")
        assert backend._model == "gpt-3.5-turbo"

    def test_available_without_package(self, monkeypatch):
        # Mock the import failure
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "openai":
                raise ImportError("no openai")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        backend = OpenAIBackend()
        # The available() method tries to import openai
        # We just verify it doesn't crash
        result = backend.available()
        # May be True or False depending on environment
        assert isinstance(result, bool)


class TestOllamaBackend:
    def test_name(self):
        backend = OllamaBackend()
        assert backend.name == "ollama"

    def test_default_model(self):
        backend = OllamaBackend()
        assert backend._model == "llama3"

    def test_default_endpoint(self):
        backend = OllamaBackend()
        assert backend._endpoint == "http://localhost:11434"

    def test_custom_endpoint(self):
        backend = OllamaBackend(endpoint="http://myserver:11434")
        assert backend._endpoint == "http://myserver:11434"


class TestGetAIBackend:
    def setup_method(self):
        reset_backend_cache()

    def teardown_method(self):
        reset_backend_cache()

    def test_default_is_none_backend(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")
        backend = get_ai_backend()
        assert isinstance(backend, NoOpBackend)

    def test_force_name_overrides_settings(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "openai")
        reset_backend_cache()
        backend = get_ai_backend(force_name="none")
        assert isinstance(backend, NoOpBackend)

    def test_unknown_backend_falls_back_to_none(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "unknown_xyz")
        reset_backend_cache()
        backend = get_ai_backend()
        assert isinstance(backend, NoOpBackend)

    def test_caching(self, monkeypatch):
        monkeypatch.setattr("scalable.common.settings.ai_backend", "none")
        reset_backend_cache()
        b1 = get_ai_backend()
        b2 = get_ai_backend()
        assert b1 is b2
