"""Hypothesis strategies for generating Python source code, somewhat like CSmith."""

from hypothesmith.cst import from_node
from hypothesmith.syntactic import from_grammar

__version__ = "0.2.2"
__all__ = ["from_grammar", "from_node"]
