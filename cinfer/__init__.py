"""
Cinfer - Code Specific Inference Framework
A framework for agents with inference-time grammars
"""

from .decorators import tool, depends, depends_grammar
from .agent import Agent

__all__ = ["tool", "depends", "depends_grammar", "Agent"]
