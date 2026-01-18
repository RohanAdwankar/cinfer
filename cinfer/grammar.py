"""
Grammar generation for tools and parameters
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
from .registry import ToolMetadata, registry

logger = logging.getLogger(__name__)


class GrammarGenerator:
    """Generates GBNF grammars for tools and parameters"""

    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._object_hashes: Dict[str, str] = {}

    def _escape_string(self, s: str) -> str:
        """Escape a string for use in GBNF"""
        # Escape special characters
        s = s.replace('\\', '\\\\')
        s = s.replace('"', '\\"')
        s = s.replace('\n', '\\n')
        s = s.replace('\r', '\\r')
        s = s.replace('\t', '\\t')
        return s

    def _hash_object(self, obj: Any) -> str:
        """Create a hash of an object's contents"""
        try:
            # For lists and other iterables, hash their contents
            if isinstance(obj, (list, tuple)):
                content = json.dumps(list(obj), sort_keys=True)
            else:
                content = str(obj)
            return hashlib.md5(content.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"Failed to hash object: {e}")
            return str(id(obj))

    def generate_tools_grammar(self, allow_none: bool = False) -> str:
        """
        Generate a grammar for available tool names.

        Args:
            allow_none: Whether to include "NONE" as an option

        Returns:
            GBNF grammar string
        """
        cache_key = f"tools_grammar_none_{allow_none}"

        # Check if we need to regenerate
        tools = registry.get_all_tools()
        tools_hash = self._hash_object((sorted(tools.keys()), allow_none))

        if cache_key in self._cache and self._object_hashes.get(cache_key) == tools_hash:
            logger.info("Using cached tools grammar (no changes detected)")
            return self._cache[cache_key]

        logger.info(f"Generating tools grammar for {len(tools)} tools (allow_none={allow_none})")

        if not tools:
            # No tools registered
            grammar = 'root ::= "NO_TOOLS_AVAILABLE"'
        else:
            # Create alternatives for each tool name
            tool_names = sorted(tools.keys())
            alternatives = ' | '.join([f'"{self._escape_string(name)}"' for name in tool_names])

            # Add NONE option if requested
            if allow_none:
                alternatives = f'"NONE" | {alternatives}'

            grammar = f'root ::= {alternatives}'

        # Cache the result
        self._cache[cache_key] = grammar
        self._object_hashes[cache_key] = tools_hash
        logger.debug(f"Generated grammar:\n{grammar}")

        return grammar

    def generate_parameter_grammar(self, tool_name: str, param_name: str) -> Optional[str]:
        """
        Generate a grammar for a specific parameter's valid values.

        Args:
            tool_name: Name of the tool
            param_name: Name of the parameter

        Returns:
            GBNF grammar string or None if no dependency exists
        """
        tool = registry.get_tool(tool_name)
        if not tool:
            logger.warning(f"Tool {tool_name} not found")
            return None

        dependency = tool.get_dependency(param_name)
        if not dependency:
            logger.debug(f"No dependency for {tool_name}.{param_name}")
            return None

        # If this is a raw grammar string, return it directly
        if dependency.is_grammar:
            logger.info(f"Using custom GBNF grammar for {tool_name}.{param_name} ({len(dependency.source_object)} bytes)")
            return dependency.source_object

        cache_key = f"{tool_name}_{param_name}_grammar"

        # Check if we need to regenerate
        obj_hash = self._hash_object(dependency.source_object)

        if cache_key in self._cache and self._object_hashes.get(cache_key) == obj_hash:
            logger.info(f"Using cached parameter grammar for {tool_name}.{param_name} (no changes detected)")
            return self._cache[cache_key]

        logger.info(f"Generating parameter grammar for {tool_name}.{param_name} from {dependency.source_name}")

        # Generate grammar from source object
        try:
            values = list(dependency.source_object)
            if not values:
                grammar = 'root ::= "NO_OPTIONS_AVAILABLE"'
            else:
                # Create alternatives for each valid value
                alternatives = ' | '.join([f'"{self._escape_string(str(val))}"' for val in values])
                grammar = f'root ::= {alternatives}'

            # Cache the result
            self._cache[cache_key] = grammar
            self._object_hashes[cache_key] = obj_hash
            logger.debug(f"Generated parameter grammar:\n{grammar}")

            return grammar
        except Exception as e:
            logger.error(f"Failed to generate parameter grammar: {e}")
            return None

    def _get_type_grammar(self, param_type: str) -> str:
        """Generate grammar for a parameter type"""
        # Handle basic types
        if 'int' in param_type.lower():
            return 'integer'
        elif 'float' in param_type.lower():
            return 'number'
        elif 'bool' in param_type.lower():
            return 'boolean'
        elif 'list' in param_type.lower() or 'array' in param_type.lower():
            return 'array'
        elif 'dict' in param_type.lower():
            return 'object'
        else:
            return 'string'

    def generate_tool_call_grammar(self, tool_name: str) -> str:
        """
        Generate a grammar for calling a specific tool with its parameters.

        This creates a grammar that expects the format:
        tool_name(param1="value1", param2="value2")

        Args:
            tool_name: Name of the tool

        Returns:
            GBNF grammar string
        """
        tool = registry.get_tool(tool_name)
        if not tool:
            return 'root ::= "TOOL_NOT_FOUND"'

        logger.info(f"Generating tool call grammar for {tool_name}")

        # Build parameter patterns using type hints and constraints
        param_patterns = []
        for param_name, param in tool.parameters.items():
            # Check if this parameter has a dependency (enum constraint)
            dependency = tool.get_dependency(param_name)

            if dependency and not dependency.is_grammar:
                # Use enum values from dependency
                try:
                    values = list(dependency.source_object)
                    alternatives = ' | '.join([f'"{self._escape_string(str(val))}"' for val in values])
                    param_patterns.append(f'{param_name}=({alternatives})')
                    logger.debug(f"Using enum constraint for {param_name}: {len(values)} values")
                except Exception as e:
                    logger.warning(f"Failed to use dependency for {param_name}: {e}")
                    param_patterns.append(f'{param_name}=["] [^"]* ["]')
            else:
                # Use type hint to determine grammar
                param_type = param.annotation if hasattr(param, 'annotation') else str
                type_name = str(param_type)

                if 'int' in type_name.lower():
                    # Integer: optional minus, one or more digits
                    param_patterns.append(f'{param_name}=("-"? [0-9]+)')
                elif 'float' in type_name.lower():
                    # Float: optional minus, digits, optional decimal part
                    param_patterns.append(f'{param_name}=("-"? [0-9]+ ("." [0-9]+)?)')
                elif 'bool' in type_name.lower():
                    # Boolean: true or false
                    param_patterns.append(f'{param_name}=("true" | "false")')
                elif 'list' in type_name.lower():
                    # Array: JSON array format
                    param_patterns.append(f'{param_name}=("[" [ ]* (string-value ([ ]* "," [ ]* string-value)*)? [ ]* "]")')
                else:
                    # Default: accept any quoted string
                    param_patterns.append(f'{param_name}=["] [^"]* ["]')

        if param_patterns:
            params_grammar = ' [,] [ ]* '.join(param_patterns)
            grammar = f'root ::= "{self._escape_string(tool_name)}" "(" {params_grammar} ")"\nstring-value ::= ["] [^"]* ["]'
        else:
            grammar = f'root ::= "{self._escape_string(tool_name)}" "()"'

        logger.debug(f"Generated tool call grammar:\n{grammar}")
        return grammar

    def clear_cache(self) -> None:
        """Clear the grammar cache"""
        logger.info("Clearing grammar cache")
        self._cache.clear()
        self._object_hashes.clear()


# Global grammar generator instance
grammar_generator = GrammarGenerator()
