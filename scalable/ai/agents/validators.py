"""Output validators for PydanticAI agent results.

Provides composable validation logic that goes beyond Pydantic model
validation — checking semantic correctness, completeness, and quality
of agent outputs.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

from pydantic import BaseModel

logger = logging.getLogger(__name__)

__all__ = [
    "OutputValidator",
    "validate_output",
]

T = TypeVar("T", bound=BaseModel)


class ValidationError(Exception):
    """Raised when output validation fails."""

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class OutputValidator:
    """Composable validator for agent outputs.

    Combines multiple validation rules that check semantic correctness
    beyond what Pydantic model validation provides.

    Example
    -------
    >>> validator = OutputValidator()
    >>> validator.add_rule(
    ...     lambda result: len(result.classifications) > 0,
    ...     "At least one classification required"
    ... )
    >>> validator.validate(diagnosis_output)
    """

    def __init__(self) -> None:
        self._rules: list[tuple[Callable[[Any], bool], str]] = []
        self._field_rules: dict[str, list[tuple[Callable[[Any], bool], str]]] = {}

    def add_rule(self, check: Callable[[Any], bool], message: str) -> "OutputValidator":
        """Add a global validation rule.

        Parameters
        ----------
        check : Callable[[Any], bool]
            Function that returns True if validation passes.
        message : str
            Error message if validation fails.

        Returns
        -------
        OutputValidator
            Self for chaining.
        """
        self._rules.append((check, message))
        return self

    def add_field_rule(
        self, field: str, check: Callable[[Any], bool], message: str
    ) -> "OutputValidator":
        """Add a validation rule for a specific field.

        Parameters
        ----------
        field : str
            Field name to validate.
        check : Callable
            Validation function receiving the field value.
        message : str
            Error message on failure.

        Returns
        -------
        OutputValidator
            Self for chaining.
        """
        if field not in self._field_rules:
            self._field_rules[field] = []
        self._field_rules[field].append((check, message))
        return self

    def validate(self, result: Any) -> list[str]:
        """Run all validation rules against a result.

        Parameters
        ----------
        result : Any
            The Pydantic model instance to validate.

        Returns
        -------
        list[str]
            List of validation error messages (empty if all pass).
        """
        errors: list[str] = []

        # Global rules
        for check, message in self._rules:
            try:
                if not check(result):
                    errors.append(message)
            except Exception as exc:
                errors.append(f"Validation rule error: {exc}")

        # Field-specific rules
        for field_name, rules in self._field_rules.items():
            value = getattr(result, field_name, None)
            for check, message in rules:
                try:
                    if not check(value):
                        errors.append(f"{field_name}: {message}")
                except Exception as exc:
                    errors.append(f"{field_name}: validation error: {exc}")

        return errors

    def is_valid(self, result: Any) -> bool:
        """Check if a result passes all validation rules."""
        return len(self.validate(result)) == 0


def validate_output(result: T, *, validators: list[OutputValidator] | None = None) -> tuple[bool, list[str]]:
    """Validate an agent output against standard and custom validators.

    Parameters
    ----------
    result : T
        Pydantic model instance to validate.
    validators : list[OutputValidator] | None
        Additional validators to apply.

    Returns
    -------
    tuple[bool, list[str]]
        (is_valid, list_of_error_messages)
    """
    all_errors: list[str] = []

    # Run Pydantic model validation (re-validate)
    try:
        result.model_validate(result.model_dump())
    except Exception as exc:
        all_errors.append(f"Model validation failed: {exc}")

    # Run custom validators
    if validators:
        for validator in validators:
            errors = validator.validate(result)
            all_errors.extend(errors)

    return len(all_errors) == 0, all_errors


# ---------------------------------------------------------------------------
# Pre-built validators for common patterns
# ---------------------------------------------------------------------------


def non_empty_string_validator(field: str) -> OutputValidator:
    """Create a validator ensuring a string field is non-empty."""
    v = OutputValidator()
    v.add_field_rule(field, lambda val: bool(val and val.strip()), "must not be empty")
    return v


def non_empty_list_validator(field: str, min_items: int = 1) -> OutputValidator:
    """Create a validator ensuring a list field has minimum items."""
    v = OutputValidator()
    v.add_field_rule(
        field,
        lambda val: isinstance(val, list) and len(val) >= min_items,
        f"must have at least {min_items} item(s)",
    )
    return v


def confidence_validator() -> OutputValidator:
    """Create a validator for confidence fields (must be high/medium/low)."""
    v = OutputValidator()
    v.add_rule(
        lambda result: getattr(result, "confidence", "medium") in ("high", "medium", "low"),
        "confidence must be one of: high, medium, low",
    )
    return v
