"""
Decorators for tool registration and parameter dependencies
"""

import functools
import logging
from pathlib import Path
from typing import Any, Callable, Dict
from .registry import registry

logger = logging.getLogger(__name__)


def tool(func: Callable) -> Callable:
    """
    Decorator to register a function as a tool available to the agent.

    Usage:
        @tool
        def my_function(param: str) -> str:
            return f"Result: {param}"
    """
    # Register the tool
    registry.register_tool(func)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    # Store metadata on the function for introspection
    wrapper._is_tool = True
    wrapper._tool_name = func.__name__

    return wrapper


class DependsDecorator:
    """
    Decorator to specify parameter dependencies.

    Usage:
        operations = ["sum", "mean"]

        @tool
        @depends(operation=operations)
        def data_operations(operation: str) -> str:
            return f"Performed {operation}"
    """

    def __init__(self, **kwargs):
        """
        Initialize with parameter dependencies.

        Args:
            **kwargs: param_name=source_object pairs
        """
        self.dependencies = kwargs

    def __call__(self, func: Callable) -> Callable:
        """Apply the decorator to a function"""
        func_name = func.__name__

        # Register dependencies
        for param_name, source_object in self.dependencies.items():
            # Try to get a name for the source object
            source_name = self._get_source_name(source_object)
            registry.add_dependency(func_name, param_name, source_object, source_name)
            logger.debug(f"Registered dependency: {func_name}.{param_name} -> {source_name}")

        return func

    def _get_source_name(self, obj: Any) -> str:
        """Try to get a meaningful name for the source object"""
        # Try to find the variable name in the calling frame
        # This is a best-effort approach
        import inspect

        frame = inspect.currentframe()
        try:
            # Go up through the call stack to find where the object is defined
            caller_frame = frame.f_back.f_back.f_back  # Go up past __call__ -> __init__ -> caller
            if caller_frame:
                for var_name, var_value in caller_frame.f_locals.items():
                    if var_value is obj:
                        return var_name
        finally:
            del frame

        # Fallback to a generic name
        return f"<{type(obj).__name__}>"


def depends(**kwargs):
    """
    Decorator to specify parameter dependencies on dynamic objects.

    Usage:
        operations = ["sum", "mean", "max"]

        @tool
        @depends(operation=operations)
        def data_operations(operation: str) -> str:
            return f"Performed {operation}"

    Args:
        **kwargs: parameter_name=source_object pairs where source_object
                  is an iterable containing valid values for that parameter
    """
    return DependsDecorator(**kwargs)


def depends_grammar(**kwargs):
    """
    Decorator to specify parameter dependencies using raw GBNF grammars.

    Usage:
        c_grammar = load_c_grammar()

        @tool
        @depends_grammar(content=c_grammar)
        def write_c_file(file_path: str, content: str) -> str:
            return f"Wrote C code to {file_path}"

    Args:
        **kwargs: parameter_name=grammar_string pairs where grammar_string
                  is a GBNF grammar that constrains the parameter
    """
    class GrammarDecorator:
        def __init__(self, **grammar_kwargs):
            self.grammars = grammar_kwargs

        def __call__(self, func: Callable) -> Callable:
            func_name = func.__name__

            # Register grammar dependencies
            for param_name, grammar_str in self.grammars.items():
                registry.add_dependency(func_name, param_name, grammar_str, "<custom GBNF grammar>", is_grammar=True)
                logger.debug(f"Registered grammar dependency: {func_name}.{param_name} ({len(grammar_str)} bytes)")

            return func

    return GrammarDecorator(**kwargs)


def depends_grammar_file(**kwargs):
    """
    Decorator to specify parameter dependencies using a .gbnf file path.

    Usage:
        @tool
        @depends_grammar_file(code="grammar/python_grammar/python.gbnf")
        def new_py_file(code: str) -> str:
            ...
    """

    class GrammarFileDecorator:
        def __init__(self, **grammar_kwargs):
            self.grammars = grammar_kwargs

        def __call__(self, func: Callable) -> Callable:
            func_name = func.__name__

            for param_name, grammar_path in self.grammars.items():
                path = Path(str(grammar_path)).expanduser()
                if not path.exists() or not path.is_file():
                    raise FileNotFoundError(f"Grammar file not found: {path}")
                grammar_str = path.read_text()
                registry.add_dependency(func_name, param_name, grammar_str, str(path), is_grammar=True)
                logger.debug(
                    f"Registered grammar file dependency: {func_name}.{param_name} -> {path} ({len(grammar_str)} bytes)"
                )

            return func

    return GrammarFileDecorator(**kwargs)


def depends_language(**kwargs):
    """
    Decorator to specify parameter dependencies using a known language grammar.

    Usage:
        @tool
        @depends_language(code="python")
        def new_py_file(code: str) -> str:
            ...
    """

    language_to_path: Dict[str, str] = {
        "python": "grammar/python_grammar/python.gbnf",
    }

    class LanguageDecorator:
        def __init__(self, **language_kwargs):
            self.languages = language_kwargs

        def __call__(self, func: Callable) -> Callable:
            func_name = func.__name__

            for param_name, language in self.languages.items():
                language_key = str(language).strip().lower()
                if language_key not in language_to_path:
                    raise ValueError(f"Unsupported language: {language}")
                path = Path(language_to_path[language_key]).expanduser()
                if not path.exists() or not path.is_file():
                    raise FileNotFoundError(f"Grammar file not found: {path}")
                grammar_str = path.read_text()
                source_name = f"<language:{language_key}>"
                registry.add_dependency(func_name, param_name, grammar_str, source_name, is_grammar=True)
                logger.debug(
                    f"Registered language grammar dependency: {func_name}.{param_name} -> {source_name} ({len(grammar_str)} bytes)"
                )

            return func

    return LanguageDecorator(**kwargs)
