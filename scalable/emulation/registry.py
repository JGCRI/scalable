"""Emulator registry for managing trained surrogate models."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scalable.emulation.surrogate import TrainedEmulator


@dataclass(frozen=True)
class EmulatorInfo:
    """Summary information about a registered emulator."""

    name: str
    version: str
    model_type: str
    training_samples: int
    validation_score: float
    input_names: list[str]
    output_names: list[str]
    domain_bounds: dict[str, tuple[float, float]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "model_type": self.model_type,
            "training_samples": self.training_samples,
            "validation_score": self.validation_score,
            "input_names": self.input_names,
            "output_names": self.output_names,
            "domain_bounds": self.domain_bounds,
        }


class EmulatorRegistry:
    """Manages trained emulator models with versioning and domain validation.

    Emulators are stored in a directory structure:

    .. code-block:: text

        <registry_dir>/
          <name>/
            <version>/
              metadata.json
              model.joblib (or other serialization)

    Parameters
    ----------
    registry_dir
        Path to the emulator registry directory.
    """

    def __init__(self, registry_dir: str | Path) -> None:
        self._registry_dir = Path(registry_dir)
        self._emulators: dict[str, dict[str, TrainedEmulator]] = {}
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Discover registered emulators from the filesystem."""
        if not self._registry_dir.exists():
            return
        for name_dir in self._registry_dir.iterdir():
            if not name_dir.is_dir():
                continue
            name = name_dir.name
            for version_dir in name_dir.iterdir():
                if not version_dir.is_dir():
                    continue
                meta_file = version_dir / "metadata.json"
                if meta_file.exists():
                    if name not in self._emulators:
                        self._emulators[name] = {}
                    # Metadata loaded lazily; actual model loaded on get()

    def register(
        self,
        name: str,
        emulator: TrainedEmulator,
        *,
        version: str | None = None,
        domain: dict[str, tuple[float, float]] | None = None,
    ) -> str:
        """Register a trained emulator in the registry.

        Parameters
        ----------
        name
            Logical name for the emulator (e.g., "gcam_emissions").
        emulator
            A trained emulator implementing the :class:`TrainedEmulator` protocol.
        version
            Version string. If ``None``, auto-increments from latest.
        domain
            Optional domain bounds override (defaults to emulator metadata).

        Returns
        -------
        str
            The version string assigned to this registration.
        """
        if version is None:
            existing_versions = list(self._emulators.get(name, {}).keys())
            if existing_versions:
                # Simple integer versioning
                max_v = max(int(v) for v in existing_versions if v.isdigit())
                version = str(max_v + 1)
            else:
                version = "1"

        # Store in memory
        if name not in self._emulators:
            self._emulators[name] = {}
        self._emulators[name][version] = emulator

        # Persist metadata
        meta = emulator.metadata
        version_dir = self._registry_dir / name / version
        version_dir.mkdir(parents=True, exist_ok=True)

        meta_dict = meta.to_dict()
        if domain:
            meta_dict["domain_bounds"] = {
                k: list(v) for k, v in domain.items()
            }

        (version_dir / "metadata.json").write_text(
            json.dumps(meta_dict, indent=2, default=str)
        )

        # Try to persist the model itself
        try:
            import joblib

            joblib.dump(emulator, version_dir / "model.joblib")
        except (ImportError, Exception):
            pass  # Model not serializable or joblib unavailable

        return version

    def get(
        self,
        name: str,
        *,
        version: str | None = None,
    ) -> TrainedEmulator:
        """Retrieve a registered emulator by name and optional version.

        Parameters
        ----------
        name
            Emulator name.
        version
            Specific version to retrieve. If ``None``, returns latest.

        Returns
        -------
        TrainedEmulator
            The registered emulator instance.

        Raises
        ------
        KeyError
            If the emulator or version is not found.
        """
        if name not in self._emulators or not self._emulators[name]:
            # Try loading from disk
            self._load_emulator_from_disk(name, version)

        if name not in self._emulators or not self._emulators[name]:
            raise KeyError(f"Emulator {name!r} not found in registry")

        versions = self._emulators[name]
        if version is not None:
            if version not in versions:
                raise KeyError(f"Emulator {name!r} version {version!r} not found")
            return versions[version]

        # Return latest version
        latest = max(versions.keys(), key=lambda v: int(v) if v.isdigit() else 0)
        return versions[latest]

    def _load_emulator_from_disk(self, name: str, version: str | None) -> None:
        """Attempt to load an emulator from disk."""
        name_dir = self._registry_dir / name
        if not name_dir.exists():
            return

        for version_dir in name_dir.iterdir():
            if not version_dir.is_dir():
                continue
            if version is not None and version_dir.name != version:
                continue

            model_path = version_dir / "model.joblib"
            if model_path.exists():
                try:
                    import joblib

                    emulator = joblib.load(model_path)
                    if name not in self._emulators:
                        self._emulators[name] = {}
                    self._emulators[name][version_dir.name] = emulator
                except (ImportError, Exception):
                    pass

    def list(self) -> list[EmulatorInfo]:
        """List all registered emulators with summary info."""
        results: list[EmulatorInfo] = []

        # Check in-memory emulators
        for _name, versions in self._emulators.items():
            for _ver, emulator in versions.items():
                meta = emulator.metadata
                results.append(
                    EmulatorInfo(
                        name=meta.name,
                        version=meta.version,
                        model_type=meta.model_type,
                        training_samples=meta.training_samples,
                        validation_score=meta.validation_score,
                        input_names=meta.input_names,
                        output_names=meta.output_names,
                        domain_bounds=meta.domain_bounds,
                    )
                )

        # Check filesystem for any not in memory
        if self._registry_dir.exists():
            for name_dir in self._registry_dir.iterdir():
                if not name_dir.is_dir():
                    continue
                name = name_dir.name
                for version_dir in name_dir.iterdir():
                    if not version_dir.is_dir():
                        continue
                    ver = version_dir.name
                    # Skip if already listed from memory
                    if name in self._emulators and ver in self._emulators[name]:
                        continue
                    meta_file = version_dir / "metadata.json"
                    if meta_file.exists():
                        try:
                            meta_dict = json.loads(meta_file.read_text())
                            domain = {}
                            for k, v in meta_dict.get("domain_bounds", {}).items():
                                if isinstance(v, (list, tuple)) and len(v) == 2:
                                    domain[k] = (float(v[0]), float(v[1]))
                            results.append(
                                EmulatorInfo(
                                    name=meta_dict.get("name", name),
                                    version=meta_dict.get("version", ver),
                                    model_type=meta_dict.get("model_type", "unknown"),
                                    training_samples=meta_dict.get("training_samples", 0),
                                    validation_score=meta_dict.get("validation_score", 0.0),
                                    input_names=meta_dict.get("input_names", []),
                                    output_names=meta_dict.get("output_names", []),
                                    domain_bounds=domain,
                                )
                            )
                        except (json.JSONDecodeError, Exception):
                            pass

        return results

    def validate_domain(self, name: str, inputs: dict[str, Any]) -> bool:
        """Check if inputs fall within the emulator's declared domain bounds.

        Parameters
        ----------
        name
            Emulator name.
        inputs
            Input values to validate.

        Returns
        -------
        bool
            ``True`` if all inputs are within declared bounds (or no bounds declared).
        """
        try:
            emulator = self.get(name)
        except KeyError:
            return False

        domain = emulator.metadata.domain_bounds
        if not domain:
            return True  # No bounds declared — assume valid

        for key, (lower, upper) in domain.items():
            if key in inputs:
                value = inputs[key]
                if isinstance(value, (int, float)):
                    if value < lower or value > upper:
                        return False
        return True

    def remove(self, name: str, *, version: str | None = None) -> None:
        """Remove an emulator from the registry.

        Parameters
        ----------
        name
            Emulator name to remove.
        version
            If specified, remove only this version. Otherwise remove all versions.
        """
        if name in self._emulators:
            if version is not None:
                self._emulators[name].pop(version, None)
                if not self._emulators[name]:
                    del self._emulators[name]
            else:
                del self._emulators[name]

        # Clean up filesystem
        if version is not None:
            version_dir = self._registry_dir / name / version
            if version_dir.exists():
                import shutil

                shutil.rmtree(version_dir)
        else:
            name_dir = self._registry_dir / name
            if name_dir.exists():
                import shutil

                shutil.rmtree(name_dir)


__all__ = ["EmulatorInfo", "EmulatorRegistry"]
