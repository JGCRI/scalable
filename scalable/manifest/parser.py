"""YAML loader for ``scalable.yaml`` v1 manifests.

Phase 1 responsibilities:

* Load YAML from a file path, string, or already-parsed mapping.
* Expand ``${VAR}`` and ``${VAR:-default}`` references against
  :data:`os.environ` so manifests stay portable across machines without
  templating tools.
* Reject unknown top-level keys (defense-in-depth against typos like
  ``component:``); unknown keys *inside* ``targets[*]`` are passed through
  to the provider — see Phase 1 plan §3.3 (forward compatibility for
  Phase 3 cloud / Kubernetes overlays).
* Refuse documents whose ``version:`` differs from
  :data:`scalable.manifest.schema.SCHEMA_VERSION` with a clear message.
* Build immutable :class:`~scalable.manifest.schema.ManifestModel` and
  child dataclasses; cross-field semantic checks are deferred to
  :mod:`scalable.manifest.validate`.

The parser is deterministic — given the same input bytes and environment
the resulting :class:`ManifestModel.raw` is byte-identical, which is a
prerequisite for the Phase 1 ``manifest_lock`` fingerprint computed by
:mod:`scalable.planning.dryrun`.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from .errors import ManifestParseError, ManifestSchemaError
from .schema import (
    SCHEMA_VERSION,
    ComponentConfig,
    ManifestModel,
    ProjectConfig,
    TargetConfig,
    TaskConfig,
)

__all__ = [
    "expand_env_vars",
    "load_manifest",
    "parse_manifest",
]

# Recognised top-level keys for v1. The order is preserved for diagnostic
# messages; semantically the set is what matters.
_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {"version", "project", "targets", "components", "tasks"}
)
_REQUIRED_TOP_LEVEL_KEYS: frozenset[str] = frozenset({"version", "project"})

# Recognised per-component keys. Unknown keys here are a hard error —
# component definitions are part of the schema, not provider passthrough.
_COMPONENT_KEYS: frozenset[str] = frozenset(
    {"image", "runtime", "cpus", "memory", "mounts", "env", "tags", "preload_script"}
)
_TASK_KEYS: frozenset[str] = frozenset({"component", "cache", "outputs"})
_PROJECT_KEYS: frozenset[str] = frozenset({"name", "default_storage", "local_cache"})

# ${VAR} and ${VAR:-default} expansion. Anchored to require curly braces so
# bare ``$HOME`` style sequences (which YAML users frequently want as
# literals in mounts/paths) are left untouched.
_ENV_VAR_PATTERN: re.Pattern[str] = re.compile(
    r"""
    \$\{                       # opening ${
        (?P<name>[A-Za-z_][A-Za-z0-9_]*)
        (?:                    # optional :- default form
            :-(?P<default>[^}]*)
        )?
    \}                         # closing }
    """,
    re.VERBOSE,
)


def expand_env_vars(value: Any, env: Mapping[str, str] | None = None) -> Any:
    """Recursively expand ``${VAR}`` references inside a parsed YAML tree.

    Parameters
    ----------
    value : Any
        A parsed YAML value (``str``, ``int``, ``bool``, ``None``,
        ``list``, ``dict``).
    env : Mapping[str, str] | None
        Environment to resolve against. Defaults to :data:`os.environ`.
        An explicit, restricted mapping is supported so unit tests stay
        deterministic.

    Returns
    -------
    Any
        A value of the same shape, with ``${VAR}`` references replaced.

    Raises
    ------
    ManifestParseError
        If a ``${VAR}`` reference has no value and no ``${VAR:-default}``
        clause was provided.
    """
    environment = os.environ if env is None else env

    def _expand_str(s: str) -> str:
        def _sub(match: re.Match[str]) -> str:
            name = match.group("name")
            default = match.group("default")
            if name in environment:
                return environment[name]
            if default is not None:
                return default
            raise ManifestParseError(
                f"environment variable {name!r} referenced in manifest "
                f"is not set and no default (${{{name}:-...}}) was provided"
            )

        return _ENV_VAR_PATTERN.sub(_sub, s)

    if isinstance(value, str):
        return _expand_str(value)
    if isinstance(value, list):
        return [expand_env_vars(item, env) for item in value]
    if isinstance(value, dict):
        return {k: expand_env_vars(v, env) for k, v in value.items()}
    return value


def load_manifest(
    source: str | os.PathLike[str],
    *,
    env: Mapping[str, str] | None = None,
) -> ManifestModel:
    """Load and parse a manifest from a filesystem path.

    Parameters
    ----------
    source : str or path-like
        Path to a ``scalable.yaml`` document.
    env : Mapping[str, str] | None
        Optional environment override for ``${VAR}`` expansion. Defaults
        to :data:`os.environ`.

    Returns
    -------
    ManifestModel
        A frozen, immutable model.

    Raises
    ------
    ManifestParseError
        If the file cannot be read or the YAML is malformed.
    ManifestSchemaError
        If the document violates the v1 schema.
    """
    path = Path(source)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - exercised via integration
        raise ManifestParseError(
            f"could not read manifest at {path!s}: {exc}"
        ) from exc
    return parse_manifest(text, env=env, source_path=str(path))


def parse_manifest(
    source: str | Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    source_path: str | None = None,
) -> ManifestModel:
    """Parse a manifest from a YAML string or already-parsed mapping.

    Parameters
    ----------
    source : str or Mapping
        Either a YAML document as a string or an already-loaded mapping.
        Tests usually pass a mapping directly so they don't depend on
        round-tripping YAML.
    env : Mapping[str, str] | None
        Environment override for ``${VAR}`` expansion.
    source_path : str | None
        Optional originating file path (carried into ``ManifestModel``).

    Returns
    -------
    ManifestModel
    """
    if isinstance(source, str):
        try:
            raw_doc = yaml.safe_load(source)
        except yaml.YAMLError as exc:
            raise ManifestParseError(f"malformed YAML: {exc}") from exc
    else:
        raw_doc = dict(source)

    if raw_doc is None:
        raise ManifestSchemaError("manifest document is empty")
    if not isinstance(raw_doc, dict):
        raise ManifestSchemaError(
            f"manifest must be a mapping at the top level, got {type(raw_doc).__name__}"
        )

    expanded = expand_env_vars(raw_doc, env=env)
    if not isinstance(expanded, dict):  # pragma: no cover - defensive
        raise ManifestSchemaError("manifest top-level must remain a mapping after expansion")

    _check_top_level_keys(expanded)
    _check_version(expanded)

    project = _build_project(expanded.get("project") or {})
    targets = _build_targets(expanded.get("targets") or {})
    components = _build_components(expanded.get("components") or {})
    tasks = _build_tasks(expanded.get("tasks") or {})

    return ManifestModel(
        version=int(expanded["version"]),
        project=project,
        targets=targets,
        components=components,
        tasks=tasks,
        raw=expanded,
        source_path=source_path,
    )


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------


def _check_top_level_keys(doc: Mapping[str, Any]) -> None:
    unknown = set(doc) - _TOP_LEVEL_KEYS
    if unknown:
        raise ManifestSchemaError(
            "unknown top-level manifest key(s): "
            + ", ".join(sorted(unknown))
            + f" (allowed: {sorted(_TOP_LEVEL_KEYS)})"
        )
    missing = _REQUIRED_TOP_LEVEL_KEYS - set(doc)
    if missing:
        raise ManifestSchemaError(
            "manifest missing required top-level key(s): " + ", ".join(sorted(missing))
        )


def _check_version(doc: Mapping[str, Any]) -> None:
    version = doc.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise ManifestSchemaError(
            f"manifest 'version' must be an integer, got {type(version).__name__}"
        )
    if version != SCHEMA_VERSION:
        raise ManifestSchemaError(
            f"manifest schema version {version!r} is not supported by this "
            f"Scalable build (expected {SCHEMA_VERSION}). Upgrade Scalable or "
            "downgrade the manifest."
        )


def _require_mapping(value: Any, *, where: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ManifestSchemaError(
            f"{where} must be a mapping, got {type(value).__name__}"
        )
    return dict(value)


def _build_project(value: Any) -> ProjectConfig:
    block = _require_mapping(value, where="'project'")
    unknown = set(block) - _PROJECT_KEYS
    if unknown:
        raise ManifestSchemaError(
            f"unknown 'project' key(s): {', '.join(sorted(unknown))} "
            f"(allowed: {sorted(_PROJECT_KEYS)})"
        )
    name = block.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ManifestSchemaError("'project.name' is required and must be a non-empty string")
    default_storage = block.get("default_storage")
    if default_storage is not None and not isinstance(default_storage, str):
        raise ManifestSchemaError("'project.default_storage' must be a string when set")
    local_cache = block.get("local_cache")
    if local_cache is not None and not isinstance(local_cache, str):
        raise ManifestSchemaError("'project.local_cache' must be a string when set")
    return ProjectConfig(
        name=name.strip(),
        default_storage=default_storage,
        local_cache=local_cache,
    )


def _build_targets(value: Any) -> dict[str, TargetConfig]:
    block = _require_mapping(value, where="'targets'")
    out: dict[str, TargetConfig] = {}
    for tname, tspec in block.items():
        if not isinstance(tname, str) or not tname:
            raise ManifestSchemaError(f"target name must be a non-empty string, got {tname!r}")
        spec_map = _require_mapping(tspec, where=f"'targets.{tname}'")
        provider = spec_map.pop("provider", None)
        if not isinstance(provider, str) or not provider:
            raise ManifestSchemaError(
                f"'targets.{tname}.provider' is required and must be a string"
            )
        # Everything else is provider-specific options. We deliberately do
        # not validate keys here so Phase 3 cloud overlays can carry
        # forward-compatible fields without a parser change. The validator
        # surfaces unknown keys as warnings.
        out[tname] = TargetConfig(name=tname, provider=provider, options=dict(spec_map))
    return out


def _build_components(value: Any) -> dict[str, ComponentConfig]:
    block = _require_mapping(value, where="'components'")
    out: dict[str, ComponentConfig] = {}
    for cname, cspec in block.items():
        if not isinstance(cname, str) or not cname:
            raise ManifestSchemaError(
                f"component name must be a non-empty string, got {cname!r}"
            )
        spec_map = _require_mapping(cspec, where=f"'components.{cname}'")
        unknown = set(spec_map) - _COMPONENT_KEYS
        if unknown:
            raise ManifestSchemaError(
                f"unknown 'components.{cname}' key(s): {', '.join(sorted(unknown))} "
                f"(allowed: {sorted(_COMPONENT_KEYS)})"
            )
        cpus_value = spec_map.get("cpus", 1)
        if not isinstance(cpus_value, int) or isinstance(cpus_value, bool) or cpus_value < 1:
            raise ManifestSchemaError(
                f"'components.{cname}.cpus' must be a positive integer (got {cpus_value!r})"
            )
        image_value = spec_map.get("image")
        if image_value is not None and not isinstance(image_value, str):
            raise ManifestSchemaError(
                f"'components.{cname}.image' must be a string when set"
            )
        runtime_value = spec_map.get("runtime")
        if runtime_value is not None and not isinstance(runtime_value, str):
            raise ManifestSchemaError(
                f"'components.{cname}.runtime' must be a string when set"
            )
        memory_value = spec_map.get("memory")
        if memory_value is not None and not isinstance(memory_value, str):
            raise ManifestSchemaError(
                f"'components.{cname}.memory' must be a string when set "
                f"(e.g. '8G', '500MB'); got {type(memory_value).__name__}"
            )
        mounts_value = spec_map.get("mounts") or {}
        if not isinstance(mounts_value, Mapping):
            raise ManifestSchemaError(
                f"'components.{cname}.mounts' must be a mapping of host:container paths"
            )
        env_value = spec_map.get("env") or {}
        if not isinstance(env_value, Mapping):
            raise ManifestSchemaError(
                f"'components.{cname}.env' must be a mapping of NAME:VALUE pairs"
            )
        # Coerce env values to str so later providers don't have to.
        env_map = {str(k): str(v) for k, v in env_value.items()}
        tags_value = spec_map.get("tags") or []
        if not isinstance(tags_value, list) or not all(isinstance(t, str) for t in tags_value):
            raise ManifestSchemaError(
                f"'components.{cname}.tags' must be a list of strings"
            )
        preload_value = spec_map.get("preload_script")
        if preload_value is not None and not isinstance(preload_value, str):
            raise ManifestSchemaError(
                f"'components.{cname}.preload_script' must be a string when set"
            )
        out[cname] = ComponentConfig(
            name=cname,
            image=image_value,
            runtime=runtime_value,
            cpus=cpus_value,
            memory=memory_value,
            mounts=dict(mounts_value),
            env=env_map,
            tags=list(tags_value),
            preload_script=preload_value,
        )
    return out


def _build_tasks(value: Any) -> dict[str, TaskConfig]:
    block = _require_mapping(value, where="'tasks'")
    out: dict[str, TaskConfig] = {}
    for tname, tspec in block.items():
        if not isinstance(tname, str) or not tname:
            raise ManifestSchemaError(
                f"task name must be a non-empty string, got {tname!r}"
            )
        spec_map = _require_mapping(tspec, where=f"'tasks.{tname}'")
        unknown = set(spec_map) - _TASK_KEYS
        if unknown:
            raise ManifestSchemaError(
                f"unknown 'tasks.{tname}' key(s): {', '.join(sorted(unknown))} "
                f"(allowed: {sorted(_TASK_KEYS)})"
            )
        component = spec_map.get("component")
        if not isinstance(component, str) or not component:
            raise ManifestSchemaError(
                f"'tasks.{tname}.component' is required and must be a string"
            )
        cache = spec_map.get("cache", False)
        if not isinstance(cache, bool):
            raise ManifestSchemaError(
                f"'tasks.{tname}.cache' must be a boolean when set"
            )
        outputs = spec_map.get("outputs") or {}
        if not isinstance(outputs, Mapping):
            raise ManifestSchemaError(
                f"'tasks.{tname}.outputs' must be a mapping when set"
            )
        out[tname] = TaskConfig(
            name=tname,
            component=component,
            cache=cache,
            outputs={str(k): str(v) for k, v in outputs.items()},
        )
    return out
