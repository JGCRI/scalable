"""Tool registration system for PydanticAI agents.

Provides a declarative way to register tools that agents can use during
execution, with automatic schema generation from type annotations.

Tools are functions that agents can call to gather information, perform
calculations, or interact with external systems during reasoning.
"""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

__all__ = [
    "ToolRegistry",
    "tool",
]

F = TypeVar("F", bound=Callable[..., Any])


class ToolRegistry:
    """Registry for agent tools with schema generation.

    Tools registered here can be attached to PydanticAI agents for use
    during reasoning. Each tool must be a typed function with a docstring.

    Example
    -------
    >>> registry = ToolRegistry()
    >>> @registry.register
    ... def get_resource_usage(component: str) -> dict:
    ...     '''Get current resource usage for a component.'''
    ...     return {"cpus": 4, "memory": "8G"}
    >>> registry.list_tools()
    ['get_resource_usage']
    """

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    def register(
        self,
        func: Callable[..., Any] | None = None,
        *,
        name: str | None = None,
        description: str | None = None,
        retries: int = 1,
    ) -> Any:
        """Register a tool function.

        Can be used as a decorator with or without arguments:

        >>> @registry.register
        ... def my_tool(x: int) -> str: ...

        >>> @registry.register(name="custom_name", retries=3)
        ... def another_tool(x: int) -> str: ...

        Parameters
        ----------
        func : Callable | None
            The function to register (when used without parentheses).
        name : str | None
            Override tool name (defaults to function name).
        description : str | None
            Override description (defaults to docstring).
        retries : int
            Number of retries if the tool call fails.
        """
        def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or f.__name__
            tool_desc = description or (f.__doc__ or "").strip().split("\n")[0]

            self._tools[tool_name] = f
            self._metadata[tool_name] = {
                "name": tool_name,
                "description": tool_desc,
                "retries": retries,
                "function": f,
            }
            return f

        if func is not None:
            return decorator(func)
        return decorator

    def unregister(self, name: str) -> None:
        """Remove a registered tool."""
        self._tools.pop(name, None)
        self._metadata.pop(name, None)

    def get(self, name: str) -> Callable[..., Any] | None:
        """Get a tool function by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_metadata(self, name: str) -> dict[str, Any] | None:
        """Get metadata for a registered tool."""
        return self._metadata.get(name)

    def attach_to_agent(self, agent: Any) -> None:
        """Attach all registered tools to a PydanticAI agent.

        Parameters
        ----------
        agent : pydantic_ai.Agent
            The agent to attach tools to.
        """
        for tool_name, func in self._tools.items():
            meta = self._metadata[tool_name]
            try:
                agent.tool(retries=meta.get("retries", 1))(func)
            except Exception as exc:
                logger.warning(
                    "Failed to attach tool '%s' to agent: %s", tool_name, exc
                )

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# Module-level default registry
_default_registry = ToolRegistry()


def tool(
    func: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    retries: int = 1,
) -> Any:
    """Decorator to register a function as an agent tool in the default registry.

    Example
    -------
    >>> @tool
    ... def read_telemetry(run_id: str) -> dict:
    ...     '''Read telemetry data for a specific run.'''
    ...     return load_telemetry(run_id)

    >>> @tool(name="check_resources", retries=2)
    ... def check_resources(component: str) -> dict:
    ...     '''Check resource availability for a component.'''
    ...     return get_resources(component)
    """
    return _default_registry.register(func, name=name, description=description, retries=retries)


def get_default_registry() -> ToolRegistry:
    """Get the module-level default tool registry."""
    return _default_registry
