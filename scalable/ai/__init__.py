"""AI assistant subsystem for Scalable.

This package provides AI-assisted features including:

* Component onboarding (``scalable init-component``)
* Workflow composition (``scalable compose``)
* Failure diagnosis (``scalable diagnose``)
* Plan explanation (``scalable explain``)
* Manifest migration (``scalable migrate``)

All features have a **heuristic fallback** that works without any LLM backend.
LLM enhancement is opt-in via ``SCALABLE_AI_BACKEND`` env var.
"""

from __future__ import annotations

from .backend import AIBackend, NoOpBackend, get_ai_backend
from .component_onboarding import OnboardingResult, onboard_component
from .log_diagnosis import DiagnosisResult, diagnose_run
from .manifest_migrate import MigrationResult, migrate_manifest
from .plan_explain import ExplanationResult, explain_plan
from .workflow_compose import ComposeResult, compose_workflow

__all__ = [
    "AIBackend",
    "ComposeResult",
    "DiagnosisResult",
    "ExplanationResult",
    "MigrationResult",
    "NoOpBackend",
    "OnboardingResult",
    "compose_workflow",
    "diagnose_run",
    "explain_plan",
    "get_ai_backend",
    "migrate_manifest",
    "onboard_component",
]
