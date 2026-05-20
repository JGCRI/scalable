"""Uncertainty-aware emulator dispatch routing."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from scalable.emulation.decorator import get_emulation_spec, get_original_function
from scalable.emulation.registry import EmulatorRegistry


@dataclass(frozen=True)
class EmulatorDispatchResult:
    """Result of an emulator-dispatched call with provenance."""

    result: Any
    source: str  # "emulator" | "full_model" | "cached"
    confidence: float | None
    emulator_version: str | None
    fallback_reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "confidence": self.confidence,
            "emulator_version": self.emulator_version,
            "fallback_reason": self.fallback_reason,
        }


class EmulatorDispatch:
    """Routes function calls to emulator or full model based on confidence.

    The dispatch decision follows this logic:

    1. Check if the function has an ``@emulatable`` spec
    2. Check if an emulator is registered for the function
    3. Validate that inputs are within the emulator's domain
    4. Query emulator for prediction + uncertainty
    5. If confidence ≥ threshold, return emulated result
    6. Otherwise, execute full model (or apply fallback strategy)

    Parameters
    ----------
    registry
        The :class:`EmulatorRegistry` containing trained emulators.
    confidence_threshold
        Global confidence threshold override (function-level threshold
        takes precedence if specified).
    record_provenance
        If ``True``, dispatch decisions are recorded for telemetry.
    """

    def __init__(
        self,
        registry: EmulatorRegistry,
        *,
        confidence_threshold: float = 0.9,
        record_provenance: bool = True,
    ) -> None:
        self._registry = registry
        self._confidence_threshold = confidence_threshold
        self._record_provenance = record_provenance
        self._dispatch_log: list[EmulatorDispatchResult] = []

    @property
    def dispatch_log(self) -> list[EmulatorDispatchResult]:
        """Log of all dispatch decisions made."""
        return list(self._dispatch_log)

    def execute(
        self,
        func: Callable,
        *args: Any,
        emulator_name: str | None = None,
        force_full_model: bool = False,
        **kwargs: Any,
    ) -> EmulatorDispatchResult:
        """Execute a function through the emulator dispatch pipeline.

        Parameters
        ----------
        func
            The function to execute (may be ``@emulatable``-decorated).
        *args
            Positional arguments to pass to the function.
        emulator_name
            Explicit emulator name. If ``None``, derives from function spec.
        force_full_model
            If ``True``, skip emulation and run the full model directly.
        **kwargs
            Keyword arguments to pass to the function.

        Returns
        -------
        EmulatorDispatchResult
            The result with provenance information.
        """
        spec = get_emulation_spec(func)
        original_func = get_original_function(func)

        # If forced full model or no emulation spec, run directly
        if force_full_model or spec is None:
            result = original_func(*args, **kwargs)
            dispatch_result = EmulatorDispatchResult(
                result=result,
                source="full_model",
                confidence=None,
                emulator_version=None,
                fallback_reason="forced" if force_full_model else "no_emulation_spec",
            )
            self._record(dispatch_result)
            return dispatch_result

        # Determine emulator name
        emu_name = emulator_name or spec.function_name
        threshold = spec.confidence_threshold or self._confidence_threshold

        # Try to get emulator from registry
        try:
            emulator = self._registry.get(emu_name)
        except KeyError:
            return self._fallback(
                original_func, args, kwargs, spec, reason="emulator_not_registered"
            )

        # Extract inputs for emulator from kwargs
        inputs = self._extract_inputs(spec.inputs, args, kwargs)

        # Validate domain
        if spec.domain:
            if not self._validate_domain(inputs, spec.domain):
                return self._fallback(
                    original_func, args, kwargs, spec, reason="outside_domain"
                )

        # Query emulator
        prediction = emulator.predict(inputs)

        # Check confidence
        if prediction.confidence < threshold:
            return self._fallback(
                original_func,
                args,
                kwargs,
                spec,
                reason=f"low_confidence ({prediction.confidence:.3f} < {threshold})",
            )

        # Check uncertainty requirement
        if spec.uncertainty == "required" and prediction.uncertainty_bounds is None:
            return self._fallback(
                original_func,
                args,
                kwargs,
                spec,
                reason="uncertainty_required_but_not_provided",
            )

        # Accept emulated result
        dispatch_result = EmulatorDispatchResult(
            result=prediction.outputs,
            source="emulator",
            confidence=prediction.confidence,
            emulator_version=emulator.metadata.version,
            fallback_reason=None,
        )
        self._record(dispatch_result)
        return dispatch_result

    def _fallback(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        spec: Any,
        *,
        reason: str,
    ) -> EmulatorDispatchResult:
        """Execute fallback strategy based on spec."""
        if spec.fallback == "error":
            raise RuntimeError(
                f"Emulation failed for {spec.function_name}: {reason}. "
                f"Fallback strategy is 'error'."
            )
        elif spec.fallback == "cached":
            # For now, fall through to full model (cache integration TBD)
            pass

        # Default: full_model
        result = func(*args, **kwargs)
        dispatch_result = EmulatorDispatchResult(
            result=result,
            source="full_model",
            confidence=None,
            emulator_version=None,
            fallback_reason=reason,
        )
        self._record(dispatch_result)
        return dispatch_result

    def _extract_inputs(
        self,
        input_names: list[str],
        args: tuple,
        kwargs: dict,
    ) -> dict[str, Any]:
        """Extract named inputs from function arguments."""
        inputs: dict[str, Any] = {}

        # First try kwargs
        for name in input_names:
            if name in kwargs:
                inputs[name] = kwargs[name]

        # If first arg is a dict (common pattern), try extracting from it
        if args and isinstance(args[0], dict):
            for name in input_names:
                if name not in inputs and name in args[0]:
                    inputs[name] = args[0][name]

        return inputs

    def _validate_domain(
        self,
        inputs: dict[str, Any],
        domain: dict[str, tuple[float, float]],
    ) -> bool:
        """Check if inputs are within declared domain bounds."""
        for key, (lower, upper) in domain.items():
            if key in inputs:
                value = inputs[key]
                if isinstance(value, (int, float)):
                    if value < lower or value > upper:
                        return False
        return True

    def _record(self, result: EmulatorDispatchResult) -> None:
        """Record dispatch decision for telemetry."""
        if self._record_provenance:
            self._dispatch_log.append(result)


__all__ = ["EmulatorDispatch", "EmulatorDispatchResult"]
