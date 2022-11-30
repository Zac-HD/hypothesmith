"""Hypothesis strategies for generating Python source code, somewhat like CSmith."""

import ast
import dis
import sys
import warnings
from functools import lru_cache
from importlib.resources import read_text

from hypothesis import assume, strategies as st
from hypothesis.extra.lark import LarkStrategy
from hypothesis.internal.charmap import _union_intervals
from lark import Lark
from lark.indenter import Indenter

# To update this grammar file, run
# wget https://raw.githubusercontent.com/lark-parser/lark/master/lark/grammars/python.lark -O src/hypothesmith/python.lark
with warnings.catch_warnings():
    # `read_text()` is deprecated; I'll update once I've dropped 3.8 and earlier.
    warnings.simplefilter("ignore")
    LARK_GRAMMAR = read_text("hypothesmith", "python.lark")

COMPILE_MODES = {
    "eval_input": "eval",
    "file_input": "exec",
    "stmt": "single",
    "simple_stmt": "single",
    "compound_stmt": "single",
}


def _chars_to_regex_set(s: list) -> str:
    spans = tuple((ord(c), ord(c)) for c in s)
    return "".join(
        chr(a) if a == b else f"{chr(a)}-{chr(b)}"
        for a, b in _union_intervals(spans, spans)
    )


@lru_cache()
def identifiers() -> st.SearchStrategy[str]:
    lead = []
    subs = []
    for c in map(chr, range(sys.maxunicode + 1)):
        if utf8_encodable(c) and ("_" + c).isidentifier():
            subs.append(c)  # e.g. "1"
            if c.isidentifier():
                lead.append(c)  # e.g. "a"
    pattern = f"[{_chars_to_regex_set(lead)}][{_chars_to_regex_set(subs)}]*"
    return st.from_regex(pattern, fullmatch=True)


class PythonIndenter(Indenter):
    # https://github.com/lark-parser/lark/blob/master/examples/python_parser.py
    NL_type = "_NEWLINE"
    OPEN_PAREN_types = ["LPAR", "LSQB", "LBRACE"]
    CLOSE_PAREN_types = ["RPAR", "RSQB", "RBRACE"]
    INDENT_type = "_INDENT"
    DEDENT_type = "_DEDENT"
    tab_len = 4


def utf8_encodable(terminal: str) -> bool:
    try:
        terminal.encode()
        return True
    except UnicodeEncodeError:  # pragma: no cover
        # Very rarely, a "." in some terminal regex will generate a surrogate
        # character that cannot be encoded as UTF-8.  We apply this filter to
        # ensure it doesn't happen at runtime, but don't worry about coverage.
        return False


class GrammarStrategy(LarkStrategy):
    def __init__(self, grammar: Lark, start: str, auto_target: bool):
        explicit_strategies = {
            PythonIndenter.INDENT_type: st.just(" " * PythonIndenter.tab_len),
            PythonIndenter.DEDENT_type: st.just(""),
            "NAME": identifiers(),
        }
        super().__init__(grammar, start, explicit_strategies)
        self.terminal_strategies = {
            k: v.map(lambda s: s.replace("\0", "")).filter(utf8_encodable)
            for k, v in self.terminal_strategies.items()  # type: ignore
        }
        self.auto_target = auto_target and start != "single_input"

    def do_draw(self, data):  # type: ignore
        result = super().do_draw(data)
        if self.auto_target:
            # target larger inputs - the Hypothesis engine will do a multi-objective
            # hill-climbing search using these scores to generate 'better' examples.
            nodes = list(ast.walk(ast.parse(result)))
            uniq_nodes = {type(n) for n in nodes}
            instructions = list(dis.Bytecode(compile(result, "<string>", "exec")))
            targets = data.target_observations
            for value, label in [
                (instructions, "(hypothesmith) instructions in bytecode"),
                (nodes, "(hypothesmith) total number of ast nodes"),
                (uniq_nodes, "(hypothesmith) number of unique ast node types"),
            ]:
                targets[label] = max(float(len(value)), targets.get(label, 0.0))
        return result

    def draw_symbol(self, data, symbol, draw_state):  # type: ignore
        count = len(draw_state.result)
        super().draw_symbol(data, symbol, draw_state)
        if symbol.name in COMPILE_MODES:
            try:
                compile(
                    source="".join(draw_state.result[count:]),
                    filename="<string>",
                    mode=COMPILE_MODES[symbol.name],
                )
            except SyntaxError:
                # Python's grammar doesn't actually fully describe the behaviour of the
                # CPython parser and AST-post-processor, so we just filter out errors.
                assume(False)
            except Exception as err:  # pragma: no cover
                # Attempting to compile almost-valid strings has triggered a wide range
                # of bizzare errors in CPython, especially with the new PEG parser,
                # and so we maintain this extra clause to ensure that we get a decent
                # error message out of it.
                if isinstance(err, SystemError) and (
                    sys.version_info[:3] == (3, 9, 0)
                    or sys.version_info[:3] >= (3, 9, 8)
                    and str(err) == "Negative size passed to PyUnicode_New"
                ):
                    # We've triggered https://bugs.python.org/issue42218 - it's been
                    # fixed upstream, so we'll treat it as if it were a SyntaxError.
                    # Or the new https://bugs.python.org/issue45738 which makes me
                    # wish CPython would start running proptests in CI already.
                    assume(False)
                source_code = ascii("".join(draw_state.result[count:]))
                raise type(err)(
                    f"compile({source_code}, '<string>', "
                    f"{COMPILE_MODES[symbol.name]!r}) "
                    f"raised {type(err).__name__}: {str(err)}"
                ) from err

    def gen_ignore(self, data, draw_state):  # type: ignore
        # Set a consistent 1/4 chance of generating any ignored tokens (comments,
        # whitespace, line-continuations) as part of this draw.
        # See https://github.com/HypothesisWorks/hypothesis/issues/2643 for plans
        # to do more sophisticated swarm testing for grammars, upstream.
        if data.draw(
            st.shared(
                st.sampled_from([False, True, False, False]),
                key="hypothesmith_gen_ignored",
            )
        ):
            super().gen_ignore(data, draw_state)


def from_grammar(
    start: str = "file_input", *, auto_target: bool = True
) -> st.SearchStrategy[str]:
    """Generate syntactically-valid Python source code based on the grammar.

    Valid values for ``start`` are ``"single_input"``, ``"file_input"``, or
    ``"eval_input"``; respectively a single interactive statement, a module or
    sequence of commands read from a file, and input for the eval() function.

    If ``auto_target`` is True, this strategy uses ``hypothesis.target()``
    internally to drive towards larger and more complex examples.  We recommend
    leaving this enabled, as the grammar is quite complex and only simple examples
    tend to be generated otherwise.

    .. warning::
        DO NOT EXECUTE CODE GENERATED BY THIS STRATEGY.

        It could do literally anything that running Python code is able to do,
        including changing, deleting, or uploading important data.  Arbitrary
        code can be useful, but "arbitrary code execution" can be very, very bad.
    """
    assert start in {"single_input", "file_input", "eval_input"}
    assert isinstance(auto_target, bool)
    grammar = Lark(LARK_GRAMMAR, parser="lalr", postlex=PythonIndenter(), start=start)
    return GrammarStrategy(grammar, start, auto_target)
