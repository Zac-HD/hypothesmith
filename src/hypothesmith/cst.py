"""
Generating Python source code from a syntax tree.

Thanks to Instagram for open-sourcing libCST (which is great!) and
thanks to Tolkein for the name of this module.
"""

import ast
import dis
from inspect import getfullargspec, isabstract
from tokenize import (
    Floatnumber as FLOATNUMBER_RE,
    Imagnumber as IMAGNUMBER_RE,
    Intnumber as INTNUMBER_RE,
)
from typing import Type

import libcst
from hypothesis import assume, infer, strategies as st, target
from hypothesis.strategies._internal.types import _global_type_lookup
from libcst._nodes.expression import ExpressionPosition
from libcst._nodes.statement import _INDENT_WHITESPACE_RE

from hypothesmith.syntactic import identifiers

# For some nodes, we just need to ensure that they use the appropriate regex
# pattern instead of allowing literally any string.
for node_type, pattern in {
    libcst.Float: FLOATNUMBER_RE,
    libcst.Integer: INTNUMBER_RE,
    libcst.Imaginary: IMAGNUMBER_RE,
    libcst.SimpleWhitespace: libcst._nodes.whitespace.SIMPLE_WHITESPACE_RE,
}.items():
    _strategy = st.builds(node_type, st.from_regex(pattern, fullmatch=True))
    st.register_type_strategy(node_type, _strategy)

# type-ignore comments are special in the 3.8+ (typed) ast, so boost their chances)
_comments = st.from_regex(libcst._nodes.whitespace.COMMENT_RE, fullmatch=True)
st.register_type_strategy(
    libcst.Comment, st.builds(libcst.Comment, _comments | st.just("# type: ignore"))
)

# `from_type()` has less laziness than other strategies, we we register for these
# foundational node types *before* referring to them in other strategies.
st.register_type_strategy(libcst.Name, st.builds(libcst.Name, identifiers()))
st.register_type_strategy(
    libcst.SimpleString, st.builds(libcst.SimpleString, st.text().map(repr))
)

# Ensure that ImportAlias uses Attribute nodes composed only of Name nodes.
names = st.from_type(libcst.Name)
name_only_attributes = st.one_of(
    names,
    st.builds(libcst.Attribute, names, names),
    st.builds(libcst.Attribute, st.builds(libcst.Attribute, names, names), names),
)
st.register_type_strategy(
    libcst.ImportAlias, st.builds(libcst.ImportAlias, name_only_attributes)
)


def nonempty_seq(*node: Type[libcst.CSTNode]) -> st.SearchStrategy:
    return st.lists(st.one_of(*map(st.from_type, node)), min_size=1)


# There are around 150 concrete types of CST nodes.  Delightfully, libCST uses
# dataclasses for all these classes, so we can allow the `builds` & `from_type`
# inference to provide most of our arguments for us.
# However, in some cases we want to either restrict arguments (e.g. libcst.Name),
# or supply something nastier than the default argument (e.g. libcst.SimpleWhitespace)
nonempty_whitespace = st.builds(
    libcst.SimpleWhitespace, st.from_regex(" +", fullmatch=True)
)
REGISTERED = (
    [libcst.Asynchronous, nonempty_whitespace],
    [libcst.AsName, st.from_type(libcst.Name)],
    [libcst.AnnAssign, infer, infer, infer],
    [libcst.Assign, nonempty_seq(libcst.AssignTarget)],
    [libcst.Await, infer, st.just(()), st.just(()), nonempty_whitespace],
    [libcst.Attribute, infer, infer, infer],
    [libcst.Comparison, infer, nonempty_seq(libcst.ComparisonTarget)],
    [libcst.Decorator, st.from_type(libcst.Name) | st.from_type(libcst.Attribute)],
    [libcst.EmptyLine, infer, infer, infer],
    [libcst.ExceptHandler, infer, infer, infer, infer, nonempty_whitespace, infer],
    [libcst.Global, nonempty_seq(libcst.NameItem)],
    [libcst.Import, nonempty_seq(libcst.ImportAlias)],
    [
        libcst.ImportFrom,
        st.from_type(libcst.Name) | st.from_type(libcst.Attribute),
        nonempty_seq(libcst.ImportAlias),
    ],
    [
        libcst.IndentedBlock,
        infer,
        infer,
        st.from_regex(_INDENT_WHITESPACE_RE, fullmatch=True),
    ],
    [libcst.IsNot, infer, nonempty_whitespace, infer],
    [
        libcst.MatchSingleton,
        st.builds(libcst.Name, st.sampled_from(["None", "False", "True"])),
    ],
    [libcst.NamedExpr, st.from_type(libcst.Name)],
    [
        libcst.Nonlocal,
        nonempty_seq(libcst.NameItem).map(
            lambda names: names[:-1]
            + [names[-1].with_changes(comma=libcst.MaybeSentinel.DEFAULT)]
        ),
    ],
    [libcst.NotEqual, st.just("!=")],
    [libcst.NotIn, infer, nonempty_whitespace, infer],
    [libcst.Set, nonempty_seq(libcst.Element, libcst.StarredElement)],
    [libcst.Subscript, infer, nonempty_seq(libcst.SubscriptElement)],
    [libcst.TrailingWhitespace, infer, infer],
    [libcst.With, nonempty_seq(libcst.WithItem)],
)


@st.composite
def builds_filtering(draw, t, **kwargs):  # type: ignore
    try:
        return draw(st.builds(t, **kwargs))
    except libcst.CSTValidationError:
        assume(False)


# This is where the magic happens: teach `st.from_type` to generate each node type
for node_type, *strats in REGISTERED:
    # TODO: once everything else is working, come back here and use `infer` for
    # all arguments without an explicit strategy - inference is more "interesting"
    # than just using the default argument... in the proverbial sense.
    # Mostly this will consist of ensuring that parens remain balanced.
    args = [name for name in getfullargspec(node_type).args if name != "self"]
    kwargs = dict(zip(args, strats))
    st.register_type_strategy(node_type, builds_filtering(node_type, **kwargs))

# We have special handling for `Try` nodes, because there are two options.
# If a Try node has no `except` clause, it *must* have a `finally` clause and
# *must not* have an `else` clause.  With one or more except clauses, it may
# have an else and/or a finally, or neither.
# The .map() ensures that any bare-`except:` clauses are ordered last.
st.register_type_strategy(
    libcst.Try,
    st.builds(libcst.Try, finalbody=st.from_type(libcst.Finally))
    | st.builds(
        libcst.Try,
        body=infer,
        handlers=st.lists(
            st.deferred(lambda: st.from_type(libcst.ExceptHandler)),
            min_size=1,
            unique_by=lambda caught: caught.type,
        ).map(lambda xs: sorted(xs, key=lambda x: x.type is None)),
        orelse=infer,
        finalbody=infer,
    ),
)

# Assert can either have a comma and message, or neither
st.register_type_strategy(
    libcst.Assert,
    st.builds(
        libcst.Assert,
        test=infer,
        whitespace_after_assert=nonempty_whitespace,
        semicolon=infer,
    )
    | st.builds(
        libcst.Assert,
        test=infer,
        whitespace_after_assert=nonempty_whitespace,
        comma=st.from_type(libcst.Comma),
        msg=st.from_type(libcst.BaseExpression),
        semicolon=infer,
    ),
)

# either posargs, kwargs, or **args, but only one at a time
st.register_type_strategy(
    libcst.Arg,
    st.builds(
        libcst.Arg,
        value=infer,
        comma=infer,
        star=infer,
        whitespace_after_star=infer,
        whitespace_after_arg=infer,
    )
    | st.builds(
        libcst.Arg,
        value=infer,
        keyword=st.from_type(libcst.Name),
        equal=st.from_type(libcst.AssignEqual),
        comma=infer,
        star=st.just(""),
        whitespace_after_arg=infer,
    ),
)


@st.composite
def boolean_op_with_whitespace(draw):  # type: ignore
    # for BooleanOperation, some expressions require whitespace before
    # and/or after e.g. a or b whereas (1)or(2) is OK.
    left = draw(st.from_type(libcst.BaseExpression))
    right = draw(st.from_type(libcst.BaseExpression))
    op = draw(st.from_type(libcst.BaseBooleanOp))
    if op.whitespace_before.empty and not left._safe_to_use_with_word_operator(
        ExpressionPosition.LEFT
    ):  # pragma: no cover
        op = op.with_changes(whitespace_before=libcst.SimpleWhitespace(" "))
    if op.whitespace_after.empty and not right._safe_to_use_with_word_operator(
        ExpressionPosition.RIGHT
    ):  # pragma: no cover
        op = op.with_changes(whitespace_after=libcst.SimpleWhitespace(" "))
    return libcst.BooleanOperation(left, op, right)


st.register_type_strategy(libcst.BooleanOperation, boolean_op_with_whitespace())

st.register_type_strategy(
    libcst.ComparisonTarget, builds_filtering(libcst.ComparisonTarget)
)


# TODO: this works pretty well, but it's also a pretty poor trick for performance.
#       Instead of filtering, we should continue expanding the specific node
#       strategies as used above in order to generate valid things by construction.
for t in vars(libcst).values():
    if (
        isinstance(t, type)
        and not isabstract(t)
        and issubclass(t, libcst.CSTNode)
        and t not in _global_type_lookup
    ):
        st.register_type_strategy(t, builds_filtering(t))


def record_targets(code: str) -> str:
    # target larger inputs - the Hypothesis engine will do a multi-objective
    # hill-climbing search using these scores to generate 'better' examples.
    nodes = list(ast.walk(ast.parse(code)))
    uniq_nodes = {type(n) for n in nodes}
    instructions = list(dis.Bytecode(compile(code, "<string>", "exec")))
    for value, label in [
        (len(instructions), "(hypothesmith from_node) instructions in bytecode"),
        (len(nodes), "(hypothesmith from_node) total number of ast nodes"),
        (len(uniq_nodes), "(hypothesmith from_node) number of unique ast node types"),
    ]:
        target(float(value), label=label)
    return code


def compilable(code: str, mode: str = "exec") -> bool:
    # This is used as a filter on `from_node()`, but note that LibCST aspires to
    # disallow construction of a CST node which is converted to invalid code.
    # (that is, if the resulting code would be invalid, raise an error instead)
    # See also https://github.com/Instagram/LibCST/issues/287
    try:
        compile(code, "<string>", mode)
        return True
    except (SyntaxError, ValueError):
        return False


def from_node(
    node: Type[libcst.CSTNode] = libcst.Module, *, auto_target: bool = True
) -> st.SearchStrategy[str]:
    """Generate syntactically-valid Python source code for a LibCST node type.

    You can pass any subtype of `libcst.CSTNode`.  Alternatively, you can use
    Hypothesis' built-in `from_type(node_type).map(lambda n: libcst.Module([n]).code`,
    after Hypothesmith has registered the required strategies.  However, this does
    not include automatic targeting and limitations of LibCST may lead to invalid
    code being generated.
    """
    assert issubclass(node, libcst.CSTNode)
    code = st.from_type(node).map(lambda n: libcst.Module([n]).code).filter(compilable)
    return code.map(record_targets) if auto_target else code
