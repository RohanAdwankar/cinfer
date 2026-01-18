"""
Tool Registry - Central storage for registered tools and their metadata
"""

import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ParameterDependency:
    """Represents a parameter's dependency on a dynamic object or grammar"""
    param_name: str
    source_object: Any  # The object (like a list) that contains valid values, or a grammar string
    source_name: str  # Name of the source for logging
    is_grammar: bool = False  # True if source_object is a raw GBNF grammar string


@dataclass
class ToolMetadata:
    """Metadata for a registered tool"""
    name: str
    func: Callable
    description: str
    parameters: Dict[str, inspect.Parameter]
    dependencies: List[ParameterDependency] = field(default_factory=list)

    def get_dependency(self, param_name: str) -> Optional[ParameterDependency]:
        """Get dependency for a parameter if it exists"""
        for dep in self.dependencies:
            if dep.param_name == param_name:
                return dep
        return None


class ToolRegistry:
    """Singleton registry for all tools"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._pending_dependencies = {}
        return cls._instance

    def register_tool(self, func: Callable, description: str = "") -> None:
        """Register a tool function"""
        sig = inspect.signature(func)
        tool_name = func.__name__

        metadata = ToolMetadata(
            name=tool_name,
            func=func,
            description=description or func.__doc__ or "",
            parameters=dict(sig.parameters)
        )

        # Check for pending dependencies
        if tool_name in self._pending_dependencies:
            metadata.dependencies = self._pending_dependencies[tool_name]
            del self._pending_dependencies[tool_name]

        self._tools[tool_name] = metadata
        logger.info(f"Registered tool: {tool_name} with {len(metadata.parameters)} parameters")

    def add_dependency(self, func_name: str, param_name: str, source_object: Any, source_name: str, is_grammar: bool = False) -> None:
        """Add a parameter dependency"""
        dependency = ParameterDependency(param_name, source_object, source_name, is_grammar)

        if func_name in self._tools:
            self._tools[func_name].dependencies.append(dependency)
            logger.info(f"Added dependency: {func_name}.{param_name} -> {source_name}")
        else:
            # Tool not registered yet, store for later
            if func_name not in self._pending_dependencies:
                self._pending_dependencies[func_name] = []
            self._pending_dependencies[func_name].append(dependency)

    def get_tool(self, name: str) -> Optional[ToolMetadata]:
        """Get a tool by name"""
        return self._tools.get(name)

    def get_all_tools(self) -> Dict[str, ToolMetadata]:
        """Get all registered tools"""
        return self._tools.copy()

    def clear(self) -> None:
        """Clear all registered tools (mainly for testing)"""
        self._tools.clear()
        self._pending_dependencies.clear()


# Global registry instance
registry = ToolRegistry()
