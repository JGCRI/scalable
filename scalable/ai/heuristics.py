"""Rule-based heuristic analyzers for AI assistant features.

These heuristics provide functional assistants without any LLM dependency.
They analyze file structure, build systems, error patterns, and manifest
content using deterministic rules.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "DirectoryScanResult",
    "FailureClassification",
    "classify_failure",
    "detect_language",
    "estimate_resources",
    "find_run_commands",
    "scan_model_directory",
]


# ---------------------------------------------------------------------------
# File / directory scanning
# ---------------------------------------------------------------------------

#: Build system indicators and their associated language/runtime
_BUILD_INDICATORS: dict[str, str] = {
    "CMakeLists.txt": "c++",
    "Makefile": "compiled",
    "configure": "compiled",
    "configure.ac": "compiled",
    "meson.build": "compiled",
    "setup.py": "python",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "environment.yml": "python",
    "conda.yml": "python",
    "Pipfile": "python",
    "setup.cfg": "python",
    "DESCRIPTION": "r",
    "NAMESPACE": "r",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "package.json": "javascript",
    "pom.xml": "java",
    "build.gradle": "java",
}

#: Container indicators
_CONTAINER_INDICATORS: list[str] = [
    "Dockerfile",
    "Containerfile",
    "apptainer.def",
    "singularity.def",
    ".devcontainer/devcontainer.json",
]

#: Common data directory names
_DATA_DIRS: set[str] = {
    "data", "input", "inputs", "output", "outputs", "results",
    "exe", "bin", "lib", "scratch", "tmp", "logs",
}

#: File extensions associated with languages
_EXTENSION_LANGUAGES: dict[str, str] = {
    ".py": "python",
    ".cpp": "c++",
    ".cxx": "c++",
    ".cc": "c++",
    ".c": "c",
    ".h": "c/c++",
    ".hpp": "c++",
    ".f90": "fortran",
    ".f": "fortran",
    ".for": "fortran",
    ".R": "r",
    ".r": "r",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".jl": "julia",
}


@dataclass
class DirectoryScanResult:
    """Result of scanning a model directory for onboarding."""

    path: str
    languages: list[str] = field(default_factory=list)
    build_systems: list[str] = field(default_factory=list)
    container_files: list[str] = field(default_factory=list)
    data_directories: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    run_commands: list[str] = field(default_factory=list)
    has_readme: bool = False
    has_tests: bool = False
    estimated_cpus: int = 1
    estimated_memory: str = "4G"
    suggested_runtime: str | None = None
    suggested_base_image: str | None = None
    suggested_mounts: dict[str, str] = field(default_factory=dict)
    suggested_env: dict[str, str] = field(default_factory=dict)
    suggested_tags: list[str] = field(default_factory=list)
    confidence: str = "low"


def scan_model_directory(path: str | Path) -> DirectoryScanResult:
    """Scan a model directory and extract onboarding metadata.

    Parameters
    ----------
    path : str | Path
        Path to the model directory to analyze.

    Returns
    -------
    DirectoryScanResult
        Structured analysis of the model directory.
    """
    root = Path(path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Directory not found: {root}")

    result = DirectoryScanResult(path=str(root))

    # Scan top-level and one level deep
    _scan_files(root, result)
    _detect_languages(root, result)
    _estimate_resources(result)
    _suggest_container(result)
    _suggest_mounts(root, result)
    _suggest_tags(result)
    _assess_confidence(result)

    return result


def _scan_files(root: Path, result: DirectoryScanResult) -> None:
    """Scan directory structure for indicators."""
    for name in sorted(os.listdir(root)):
        full_path = root / name

        # Build system files
        if name in _BUILD_INDICATORS:
            result.build_systems.append(name)

        # Container files
        if name in _CONTAINER_INDICATORS:
            result.container_files.append(name)

        # Data directories
        if full_path.is_dir() and name.lower() in _DATA_DIRS:
            result.data_directories.append(name)

        # README
        if name.lower().startswith("readme"):
            result.has_readme = True

        # Tests
        if name.lower() in ("tests", "test", "testing"):
            result.has_tests = True

        # Config files
        if name.endswith((".xml", ".yml", ".yaml", ".cfg", ".ini", ".conf", ".toml")):
            if name not in _BUILD_INDICATORS:
                result.config_files.append(name)

    # Check for Dockerfile in subdirectories
    for container_file in _CONTAINER_INDICATORS:
        if (root / container_file).exists():
            if container_file not in result.container_files:
                result.container_files.append(container_file)


def _detect_languages(root: Path, result: DirectoryScanResult) -> None:
    """Detect programming languages from file extensions."""
    lang_counts: dict[str, int] = {}

    for dirpath, _, filenames in os.walk(root):
        # Skip hidden dirs and common non-source dirs
        rel = os.path.relpath(dirpath, root)
        if any(part.startswith(".") for part in Path(rel).parts):
            continue
        if any(part in {"node_modules", "__pycache__", "venv", ".venv", "build", "dist"}
               for part in Path(rel).parts):
            continue

        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in _EXTENSION_LANGUAGES:
                lang = _EXTENSION_LANGUAGES[ext]
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

    # Also detect from build system files
    for bs in result.build_systems:
        if bs in _BUILD_INDICATORS:
            lang = _BUILD_INDICATORS[bs]
            lang_counts[lang] = lang_counts.get(lang, 0) + 10  # weight build files

    # Sort by count, take top languages
    sorted_langs = sorted(lang_counts.items(), key=lambda x: -x[1])
    result.languages = [lang for lang, _ in sorted_langs[:5]]


def _estimate_resources(result: DirectoryScanResult) -> None:
    """Estimate resource needs based on detected language/build system."""
    if any(lang in result.languages for lang in ("c++", "c", "fortran", "compiled")):
        result.estimated_cpus = 6
        result.estimated_memory = "20G"
    elif "java" in result.languages:
        result.estimated_cpus = 4
        result.estimated_memory = "16G"
    elif "python" in result.languages:
        result.estimated_cpus = 2
        result.estimated_memory = "8G"
    elif "r" in result.languages:
        result.estimated_cpus = 2
        result.estimated_memory = "8G"
    else:
        result.estimated_cpus = 1
        result.estimated_memory = "4G"


def _suggest_container(result: DirectoryScanResult) -> None:
    """Suggest container runtime and base image."""
    if result.container_files:
        if any("apptainer" in f or "singularity" in f for f in result.container_files):
            result.suggested_runtime = "apptainer"
        else:
            result.suggested_runtime = "docker"
    else:
        result.suggested_runtime = "docker"

    # Suggest base image
    primary_lang = result.languages[0] if result.languages else None
    if primary_lang in ("c++", "c", "compiled", "fortran"):
        result.suggested_base_image = "ubuntu:22.04"
    elif primary_lang == "python":
        result.suggested_base_image = "python:3.11-slim"
    elif primary_lang == "r":
        result.suggested_base_image = "rocker/r-ver:4.3"
    elif primary_lang == "java":
        result.suggested_base_image = "eclipse-temurin:17-jre"
    else:
        result.suggested_base_image = "ubuntu:22.04"


def _suggest_mounts(root: Path, result: DirectoryScanResult) -> None:
    """Suggest mount points based on data directories."""
    for ddir in result.data_directories:
        host_path = str(root / ddir)
        container_path = f"/{ddir}"
        result.suggested_mounts[host_path] = container_path

    # If there's an exe directory, mount it
    exe_dir = root / "exe"
    if exe_dir.is_dir():
        result.suggested_mounts[str(exe_dir)] = "/app/exe"


def _suggest_tags(result: DirectoryScanResult) -> None:
    """Suggest component tags from detected characteristics."""
    tags: list[str] = []
    if any(lang in result.languages for lang in ("c++", "c", "fortran", "compiled")):
        tags.append("compiled")
    if "python" in result.languages:
        tags.append("python")
    if "r" in result.languages:
        tags.append("r-lang")
    if result.estimated_memory and int(re.sub(r"[^\d]", "", result.estimated_memory)) >= 16:
        tags.append("memory-intensive")
    if result.estimated_cpus >= 4:
        tags.append("cpu-intensive")
    result.suggested_tags = tags


def _assess_confidence(result: DirectoryScanResult) -> None:
    """Assess overall confidence in the scan results."""
    score = 0
    if result.languages:
        score += 2
    if result.build_systems:
        score += 2
    if result.container_files:
        score += 2
    if result.has_readme:
        score += 1
    if result.data_directories:
        score += 1
    if result.config_files:
        score += 1

    if score >= 6:
        result.confidence = "high"
    elif score >= 3:
        result.confidence = "medium"
    else:
        result.confidence = "low"


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------


def detect_language(path: str | Path) -> list[str]:
    """Detect programming languages used in a directory."""
    result = DirectoryScanResult(path=str(path))
    _detect_languages(Path(path), result)
    return result.languages


# ---------------------------------------------------------------------------
# Resource estimation
# ---------------------------------------------------------------------------


def estimate_resources(languages: list[str]) -> dict[str, Any]:
    """Estimate resources based on detected languages."""
    result = DirectoryScanResult(path="")
    result.languages = languages
    _estimate_resources(result)
    return {
        "cpus": result.estimated_cpus,
        "memory": result.estimated_memory,
    }


# ---------------------------------------------------------------------------
# Run command detection
# ---------------------------------------------------------------------------


def find_run_commands(path: str | Path) -> list[str]:
    """Find likely run commands from Makefiles, scripts, and READMEs."""
    root = Path(path)
    commands: list[str] = []

    # Check Makefile for run/execute targets
    makefile = root / "Makefile"
    if makefile.exists():
        content = makefile.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r"^(run|execute|start|main)\s*:", content, re.MULTILINE):
            target = match.group(1)
            commands.append(f"make {target}")

    # Check for shell scripts
    for script in root.glob("*.sh"):
        if script.name.startswith(("run", "start", "execute", "launch")):
            commands.append(f"./{script.name}")

    # Check for Python entry points in pyproject.toml
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r'\[project\.scripts\]\s*\n([^\[]+)', content):
            for line in match.group(1).splitlines():
                if "=" in line:
                    cmd_name = line.split("=")[0].strip().strip('"')
                    if cmd_name:
                        commands.append(cmd_name)

    # Check for main.py or similar entry points
    for candidate in ["main.py", "run.py", "app.py", "__main__.py"]:
        if (root / candidate).exists():
            commands.append(f"python {candidate}")

    return commands


# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------

#: Failure classification patterns
_FAILURE_PATTERNS: list[tuple[str, list[str]]] = [
    ("oom", [
        r"out of memory",
        r"oom",
        r"memory.*exceeded",
        r"killed.*signal\s*9",
        r"sigkill",
        r"cannot allocate memory",
        r"std::bad_alloc",
        r"java\.lang\.OutOfMemoryError",
        r"MemoryError",
    ]),
    ("walltime", [
        r"wall.*time.*exceeded",
        r"time.*limit",
        r"DUE TO TIME LIMIT",
        r"TIMEOUT",
        r"exceeded.*walltime",
        r"job.*timed?\s*out",
    ]),
    ("mount_missing", [
        r"no such file or directory.*(/[a-zA-Z])",
        r"FileNotFoundError",
        r"mount.*not.*found",
        r"bind.*source.*not",
        r"ENOENT",
    ]),
    ("import_error", [
        r"ModuleNotFoundError",
        r"ImportError",
        r"No module named",
        r"cannot import name",
    ]),
    ("connection", [
        r"connection.*refused",
        r"connection.*reset",
        r"connection.*timed?\s*out",
        r"worker.*failed.*connect",
        r"scheduler.*unreachable",
        r"could not connect",
    ]),
    ("credential", [
        r"access.*denied",
        r"permission.*denied",
        r"credential.*expired",
        r"unauthorized",
        r"forbidden",
        r"403",
        r"401",
    ]),
    ("model_runtime", [
        r"runtime.*error",
        r"segmentation.*fault",
        r"core.*dumped",
        r"abort",
        r"assertion.*failed",
        r"invalid.*argument",
    ]),
]


@dataclass
class FailureClassification:
    """Classified failure with evidence and suggested fixes."""

    failure_class: str
    confidence: str
    evidence: list[str]
    suggested_fixes: list[str]
    related_context: dict[str, Any] = field(default_factory=dict)


def classify_failure(
    *,
    failure_class: str | None = None,
    message: str = "",
    details: dict[str, Any] | None = None,
    task_events: list[dict[str, Any]] | None = None,
    resource_events: list[dict[str, Any]] | None = None,
) -> FailureClassification:
    """Classify a failure and suggest fixes using rule-based heuristics.

    Parameters
    ----------
    failure_class : str | None
        Pre-classified failure class from telemetry (may be generic).
    message : str
        Error message text to analyze.
    details : dict | None
        Additional failure context.
    task_events : list | None
        Related task events for context.
    resource_events : list | None
        Related resource events for context.

    Returns
    -------
    FailureClassification
        Classified failure with evidence and suggested fixes.
    """
    details = details or {}
    task_events = task_events or []
    resource_events = resource_events or []

    # Try pattern matching on the message
    detected_class = "unknown"
    evidence: list[str] = []
    confidence = "low"

    combined_text = f"{failure_class or ''} {message} {str(details)}"

    for cls_name, patterns in _FAILURE_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, combined_text, re.IGNORECASE):
                detected_class = cls_name
                evidence.append(f"Pattern match: {pattern!r} in error text")
                confidence = "high" if len(evidence) > 1 else "medium"
                break
        if detected_class != "unknown":
            break

    # Enhance with resource context
    if resource_events:
        for rev in resource_events:
            mem = rev.get("requested_memory")
            cpus = rev.get("requested_cpus")
            if mem:
                evidence.append(f"Requested memory: {mem}")
            if cpus:
                evidence.append(f"Requested CPUs: {cpus}")

    # Generate fixes based on classification
    suggested_fixes = _generate_fixes(detected_class, evidence, details)

    return FailureClassification(
        failure_class=detected_class,
        confidence=confidence,
        evidence=evidence,
        suggested_fixes=suggested_fixes,
        related_context=details,
    )


def _generate_fixes(failure_class: str, evidence: list[str], details: dict[str, Any]) -> list[str]:
    """Generate suggested fixes based on failure classification."""
    fixes: list[str] = []

    if failure_class == "oom":
        fixes.append("Increase component memory in scalable.yaml (e.g., memory: '32G')")
        fixes.append("Run: scalable validate scalable.yaml --target <target>")
        fixes.append("Consider splitting the task into smaller chunks")

    elif failure_class == "walltime":
        fixes.append("Increase walltime in target options (e.g., walltime: '04:00:00')")
        fixes.append("Consider parallelizing the workload across more workers")
        fixes.append("Check if the task is stuck in an infinite loop")

    elif failure_class == "mount_missing":
        fixes.append("Check mount paths in component definition exist on the host")
        fixes.append("Verify container mount targets match expected paths")
        fixes.append("Run: scalable validate scalable.yaml --target <target>")

    elif failure_class == "import_error":
        fixes.append("Ensure the required package is installed in the container image")
        fixes.append("Update the component image to include missing dependencies")
        fixes.append("Check that preload_script installs needed packages")

    elif failure_class == "connection":
        fixes.append("Check network connectivity between scheduler and workers")
        fixes.append("Verify firewall/security group rules allow Dask ports")
        fixes.append("Increase worker startup timeout")

    elif failure_class == "credential":
        fixes.append("Check cloud credential configuration and expiry")
        fixes.append("Verify service account permissions")
        fixes.append("Refresh authentication tokens")

    elif failure_class == "model_runtime":
        fixes.append("Check model input files and configuration")
        fixes.append("Verify the model executable runs correctly outside Scalable")
        fixes.append("Check component environment variables")

    else:
        fixes.append("Review the full error message and stack trace")
        fixes.append("Run: scalable report --latest for run context")
        fixes.append("Check worker logs for additional details")

    return fixes
