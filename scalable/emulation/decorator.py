"""@emulatable decorator for marking functions as emulation-capable."""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Module-level registry of emulatable functions
_EMULATABLE_REGISTRY: dict[str, EmulationSpec] = {}


@dataclass(frozen=True)
class EmulationSpec:
    """Specification for an emulatable function."""

    function_name: str
    tag: str
    inputs: list[str]
    outputs: list[str]
    uncertainty: str  # "required" | "optional" | "none"
    fallback: str  # "full_model" | "error" | "cached"
    domain: dict[str, tuple[float, float]]
    confidence_threshold: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "function_name": self.function_name,
            "tag": self.tag,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "uncertainty": self.uncertainty,
            "fallback": self.fallback,
            "domain": {k: list(v) for k, v in self.domain.items()},
            "confidence_threshold": self.confidence_threshold,
        }


def emulatable(
    *,
    tag: str,
    inputs: list[str],
    outputs: list[str],
    uncertainty: str = "required",
    fallback: str = "full_model",
    domain: dict[str, tuple[float, float]] | None = None,
    confidence_threshold: float = 0.9,
) -> Callable:
    """Decorator marking a function as emulation-capable.

    When a trained emulator is available and its confidence exceeds the
    threshold, the function call can be routed to the emulator instead of
    the full model. Provenance is recorded for every dispatch decision.

    Parameters
    ----------
    tag
        Component tag for worker routing.
    inputs
        List of input parameter names the emulator expects.
    outputs
        List of output names the emulator produces.
    uncertainty
        Uncertainty requirement: ``"required"`` means emulator must provide
        calibrated uncertainty bounds; ``"optional"`` allows point estimates;
        ``"none"`` skips uncertainty checks.
    fallback
        Fallback strategy when emulator is unavailable or confidence is low:
        ``"full_model"`` runs the original function; ``"error"`` raises;
        ``"cached"`` attempts cache lookup.
    domain
        Optional domain bounds for input validation. Dict mapping input
        names to (min, max) tuples.
    confidence_threshold
        Minimum confidence for emulator predictions to be accepted.

    Examples
    --------
    >>> @emulatable(
    ...     tag="gcam",
    ...     inputs=["carbon_price", "population", "gdp"],
    ...     outputs=["emissions", "energy_price"],
    ...     uncertainty="required",
    ...     fallback="full_model",
    ...     confidence_threshold=0.9,
    ... )
    ... def run_gcam_scenario(params):
    ...     ...
    """
    valid_uncertainty = {"required", "optional", "none"}
    valid_fallback = {"full_model", "error", "cached"}

    if uncertainty not in valid_uncertainty:
        raise ValueError(
            f"uncertainty must be one of {sorted(valid_uncertainty)}, got {uncertainty!r}"
        )
    if fallback not in valid_fallback:
        raise ValueError(
            f"fallback must be one of {sorted(valid_fallback)}, got {fallback!r}"
        )
    if not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError(
            f"confidence_threshold must be between 0.0 and 1.0, got {confidence_threshold}"
        )

    def decorator(func: Callable) -> Callable:
        spec = EmulationSpec(
            function_name=func.__qualname__,
            tag=tag,
            inputs=inputs,
            outputs=outputs,
            uncertainty=uncertainty,
            fallback=fallback,
            domain=domain or {},
            confidence_threshold=confidence_threshold,
        )

        # Register in module-level registry
        _EMULATABLE_REGISTRY[func.__qualname__] = spec

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # The actual dispatch logic is handled by EmulatorDispatch
            # when invoked through a session. Direct calls run the full model.
            return func(*args, **kwargs)

        # Attach spec as metadata
        wrapper._emulation_spec = spec  # type: ignore[attr-defined]
        wrapper._original_func = func  # type: ignore[attr-defined]
        return wrapper

    return decorator


def get_emulation_spec(func: Callable) -> EmulationSpec | None:
    """Retrieve the emulation spec for a decorated function, if any."""
    return getattr(func, "_emulation_spec", None)


def get_original_function(func: Callable) -> Callable:
    """Get the original unwrapped function from an @emulatable-decorated callable."""
    return getattr(func, "_original_func", func)


def list_emulatable_functions() -> dict[str, EmulationSpec]:
    """Return all registered emulatable function specs."""
    return dict(_EMULATABLE_REGISTRY)


__all__ = [
    "EmulationSpec",
    "emulatable",
    "get_emulation_spec",
    "get_original_function",
    "list_emulatable_functions",
]
