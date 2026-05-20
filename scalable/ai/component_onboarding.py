"""AI-assisted component onboarding for Scalable.

Inspects a model directory and proposes a ``ComponentConfig``-compatible
YAML block for inclusion in ``scalable.yaml``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .backend import AIBackend, get_ai_backend
from .heuristics import DirectoryScanResult, find_run_commands, scan_model_directory
from .prompts.onboarding import ANALYSIS_PROMPT, SYSTEM_PROMPT

__all__ = ["OnboardingResult", "onboard_component"]


@dataclass
class OnboardingResult:
    """Result of AI-assisted component onboarding."""

    name: str
    component_yaml: str
    scan: DirectoryScanResult
    method: str  # "heuristic" or "ai-enhanced"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return the component as a parsed dictionary."""
        try:
            parsed = yaml.safe_load(self.component_yaml)
            if isinstance(parsed, dict):
                return parsed
            return {self.name: {}}
        except Exception:
            return {self.name: {}}


def onboard_component(
    path: str | Path,
    *,
    name: str | None = None,
    backend: AIBackend | None = None,
    no_ai: bool = False,
) -> OnboardingResult:
    """Onboard a model component by analyzing its directory.

    Parameters
    ----------
    path : str | Path
        Path to the model directory to analyze.
    name : str | None
        Component name. Defaults to the directory basename.
    backend : AIBackend | None
        AI backend to use. Defaults to configured backend.
    no_ai : bool
        If True, skip LLM enhancement and use heuristics only.

    Returns
    -------
    OnboardingResult
        Proposed component manifest with metadata.
    """
    root = Path(path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Directory not found: {root}")

    component_name = name or root.name.lower().replace(" ", "-").replace("_", "-")

    # Scan the directory
    scan = scan_model_directory(root)
    scan.run_commands = find_run_commands(root)

    # Try AI enhancement if available
    if not no_ai:
        ai_backend = backend or get_ai_backend()
        if ai_backend.available():
            return _onboard_with_ai(component_name, scan, ai_backend)

    # Heuristic-only path
    return _onboard_heuristic(component_name, scan)


def _onboard_heuristic(name: str, scan: DirectoryScanResult) -> OnboardingResult:
    """Generate component YAML using heuristic analysis only."""
    component: dict[str, Any] = {}

    if scan.suggested_base_image:
        component["image"] = f"# TODO: build image based on {scan.suggested_base_image}"

    if scan.suggested_runtime:
        component["runtime"] = scan.suggested_runtime

    component["cpus"] = scan.estimated_cpus
    component["memory"] = scan.estimated_memory

    if scan.suggested_mounts:
        component["mounts"] = dict(scan.suggested_mounts)

    env: dict[str, str] = {}
    if scan.estimated_cpus > 1:
        env["OMP_NUM_THREADS"] = str(scan.estimated_cpus)
    if env:
        component["env"] = env

    if scan.suggested_tags:
        component["tags"] = scan.suggested_tags

    # Build YAML output with comments
    lines = [
        f"# Proposed component: {name}",
        f"# Detected: {', '.join(scan.languages) if scan.languages else 'unknown language'}",
        f"# Build systems: {', '.join(scan.build_systems) if scan.build_systems else 'none detected'}",
        f"# Confidence: {scan.confidence}",
    ]
    if scan.run_commands:
        lines.append(f"# Likely run commands: {', '.join(scan.run_commands[:3])}")
    lines.append("")

    yaml_body = yaml.dump(
        {name: component}, default_flow_style=False, sort_keys=False
    )
    component_yaml = "\n".join(lines) + yaml_body

    warnings: list[str] = []
    if scan.confidence == "low":
        warnings.append("Low confidence scan - review all fields carefully")
    if not scan.container_files:
        warnings.append("No container definition found - image field needs manual setup")
    if not scan.data_directories:
        warnings.append("No data directories detected - verify mount paths")

    return OnboardingResult(
        name=name,
        component_yaml=component_yaml,
        scan=scan,
        method="heuristic",
        warnings=warnings,
    )


def _onboard_with_ai(name: str, scan: DirectoryScanResult, backend: AIBackend) -> OnboardingResult:
    """Enhance onboarding with LLM analysis."""
    # Build file listing (limited to avoid token overload)
    root = Path(scan.path)
    file_listing = _build_file_listing(root, max_files=50)

    prompt = ANALYSIS_PROMPT.format(
        path=scan.path,
        name=name,
        file_listing=file_listing,
        build_systems=", ".join(scan.build_systems) or "none",
        languages=", ".join(scan.languages) or "unknown",
        container_files=", ".join(scan.container_files) or "none",
        data_directories=", ".join(scan.data_directories) or "none",
        config_files=", ".join(scan.config_files[:10]) or "none",
    )

    try:
        response = backend.complete(prompt, system=SYSTEM_PROMPT)
        # Validate the AI response is valid YAML
        parsed = yaml.safe_load(response)
        if isinstance(parsed, dict):
            yaml_output = yaml.dump(parsed, default_flow_style=False, sort_keys=False)
            return OnboardingResult(
                name=name,
                component_yaml=yaml_output,
                scan=scan,
                method="ai-enhanced",
                warnings=["AI-generated - review all fields before use"],
            )
    except Exception:
        pass  # Fall through to heuristic

    # Fallback to heuristic if AI fails
    result = _onboard_heuristic(name, scan)
    result.warnings.append("AI enhancement failed; using heuristic fallback")
    return result


def _build_file_listing(root: Path, max_files: int = 50) -> str:
    """Build a truncated file listing for prompt context."""
    lines: list[str] = []
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden and build directories
        dirnames[:] = [d for d in dirnames if not d.startswith(".")
                       and d not in {"node_modules", "__pycache__", "venv", ".venv", "build", "dist"}]

        rel_dir = os.path.relpath(dirpath, root)
        for fname in sorted(filenames):
            if count >= max_files:
                lines.append(f"... ({count}+ files, truncated)")
                return "\n".join(lines)
            rel_path = os.path.join(rel_dir, fname) if rel_dir != "." else fname
            lines.append(f"  {rel_path}")
            count += 1

    return "\n".join(lines) if lines else "  (empty directory)"
