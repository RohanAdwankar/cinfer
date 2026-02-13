"""
Cinfer - Code Specific Inference Framework
A framework for agents with inference-time grammars
"""

from .decorators import tool, depends, depends_grammar, depends_grammar_file, depends_language
from .agent import Agent, sanitize_python_tool_code

__all__ = [
	"tool",
	"depends",
	"depends_grammar",
	"depends_grammar_file",
	"depends_language",
	"Agent",
	"sanitize_python_tool_code",
]
