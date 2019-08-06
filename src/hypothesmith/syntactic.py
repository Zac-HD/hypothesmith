"""Hypothesis strategies for generating Python source code, somewhat like CSmith."""

import urllib.request
from pathlib import Path

import hypothesis.strategies as st
from hypothesis.extra.lark import LarkStrategy
from lark import Lark
from lark.indenter import Indenter

URL = "https://raw.githubusercontent.com/lark-parser/lark/master/examples/python3.lark"
fname = Path(__file__).with_name(URL.split("/")[-1])

if fname.exists():
    with open(fname) as f:
        lark_grammar = f.read()
else:  # pragma: no cover
    # To update the grammar definition, delete the file and execute this.
    with urllib.request.urlopen(URL) as handle:
        lark_grammar = handle.read().decode()
    with open(fname, "w") as f:
        f.write(lark_grammar)


class PythonIndenter(Indenter):
    # https://github.com/lark-parser/lark/blob/master/examples/python_parser.py
    NL_type = "_NEWLINE"
    OPEN_PAREN_types = ["LPAR", "LSQB", "LBRACE"]
    CLOSE_PAREN_types = ["RPAR", "RSQB", "RBRACE"]
    INDENT_type = "_INDENT"
    DEDENT_type = "_DEDENT"
    tab_len = 4


class GrammarStrategy(LarkStrategy):
    # TODO: upstream pull request to support custom strategies for terminals.
    # https://github.com/HypothesisWorks/hypothesis/compare/master...Zac-HD:lark-python

    def __init__(
        self, grammar: str, start: str = None, explicit_strategies: dict = None
    ):
        LarkStrategy.__init__(self, grammar, start=start)  # type: ignore
        self.terminal_strategies.update(explicit_strategies or {})


def fixup(source_code: str) -> str:
    """Strip trailing whitespace and backslash if any and add ending newline."""
    return source_code.rstrip().rstrip("\\") + "\n"


def from_grammar(start: str = "file_input") -> st.SearchStrategy[str]:
    """Generate syntactically-valid Python source code based on the grammar."""
    # TODO: check that `start` is the name of a production
    # TODO: document the list of valid start names
    grammar = Lark(lark_grammar, parser="lalr", postlex=PythonIndenter(), start=start)
    explicit_strategies = dict(
        _INDENT=st.just(" " * 4),
        _DEDENT=st.just(""),
        NAME=st.from_regex(r"[a-z_A-Z]+", fullmatch=True).filter(str.isidentifier),
    )
    return GrammarStrategy(grammar, start, explicit_strategies).map(fixup)
