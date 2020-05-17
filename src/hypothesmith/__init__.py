"""Hypothesis strategies for generating Python source code, somewhat like CSmith."""

from hypothesmith.syntactic import from_grammar

try:
    from hypothesmith.cst import from_node
except Exception:  # pragma: no cover
    # allows use on Python 3.9 before libcst supports that version
    pass

__version__ = "0.1.2"
__all__ = ["from_grammar", "from_node"]
