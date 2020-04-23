"""
Generating Python source code from a syntax tree.

Thanks to Instagram for open-sourcing libCST (which is great!) and
thanks to Tolkein for the name of this module.
"""

from inspect import getfullargspec
from tokenize import (  # type: ignore
    Floatnumber as FLOATNUMBER_RE,
    Imagnumber as IMAGNUMBER_RE,
    Intnumber as INTNUMBER_RE,
)
from typing import Type, Union

import hypothesis.strategies as st
import libcst
from hypothesis import infer

from hypothesmith.syntactic import identifiers

# For some nodes, we just need to ensure that they use the appropriate regex
# pattern instead of allowing literally any string.
for node_type, pattern in {
    libcst.Float: FLOATNUMBER_RE,
    libcst.Integer: INTNUMBER_RE,
    libcst.Imaginary: IMAGNUMBER_RE,
    libcst.Comment: libcst._nodes.whitespace.COMMENT_RE,
    libcst.SimpleWhitespace: libcst._nodes.whitespace.SIMPLE_WHITESPACE_RE,
}.items():
    _strategy = st.builds(node_type, st.from_regex(pattern, fullmatch=True))
    st.register_type_strategy(node_type, _strategy)

# `from_type()` has less laziness than other strategies, we we register for these
# foundational node types *before* referring to them in other strategies.
st.register_type_strategy(libcst.Name, st.builds(libcst.Name, identifiers()))
st.register_type_strategy(
    libcst.SimpleString, st.builds(libcst.SimpleString, st.text().map(repr))
)


def nonempty_seq(node: Type[libcst.CSTNode]) -> st.SearchStrategy:
    return st.lists(st.from_type(node), min_size=1)


# There are around 150 concrete types of CST nodes.  Delightfully, libCST uses
# dataclasses for all these classes, so we can allow the `builds` & `from_type`
# inference to provide most of our arguments for us.
# However, in some cases we want to either restrict arguments (e.g. libcst.Name),
# or supply something nastier than the default argument (e.g. libcst.SimpleWhitespace)
REGISTERED = (
    [libcst.AsName, st.from_type(libcst.Name)],
    [libcst.Assign, nonempty_seq(libcst.AssignTarget)],
    [libcst.Comparison, infer, nonempty_seq(libcst.ComparisonTarget)],
    [libcst.Decorator, st.from_type(libcst.Name) | st.from_type(libcst.Attribute)],
    [libcst.Global, nonempty_seq(libcst.NameItem)],
    [libcst.Import, nonempty_seq(libcst.ImportAlias)],
    [
        libcst.ImportFrom,
        st.from_type(libcst.Name) | st.from_type(libcst.Attribute),
        nonempty_seq(libcst.ImportAlias),
    ],
    [libcst.NamedExpr, st.from_type(libcst.Name)],
    [libcst.Nonlocal, nonempty_seq(libcst.NameItem)],
    [libcst.Set, nonempty_seq(Union[libcst.Element, libcst.StarredElement])],
    [libcst.Subscript, infer, nonempty_seq(libcst.SubscriptElement)],
    [libcst.With, nonempty_seq(libcst.WithItem)],
)


# This is where the magic happens: teach `st.from_type` to generate each node type
for node_type, *strats in REGISTERED:
    # TODO: once everything else is working, come back here and use `infer` for
    # all arguments without an explicit strategy - inference is more "interesting"
    # than just using the default argument... in the proverbial sense.
    # Mostly this will consist of ensuring that parens remain balanced.
    args = [name for name in getfullargspec(node_type).args if name != "self"]
    kwargs = dict(zip(args, strats))
    st.register_type_strategy(node_type, st.builds(node_type, **kwargs))

# We have special handling for `Try` nodes, because there are two options.
# If a Try node has no `except` clause, it *must* have a `finally` clause and
# *must not* have an `else` clause.  With one or more except clauses, it may
# have an else and/or a finally, or neither.
st.register_type_strategy(
    libcst.Try,
    st.builds(libcst.Try, finalbody=st.from_type(libcst.Finally))
    | st.builds(
        libcst.Try,
        body=infer,
        handlers=st.lists(
            st.from_type(libcst.ExceptHandler),
            min_size=1,
            unique_by=lambda caught: caught.type,
        ),
        orelse=infer,
        finalbody=infer,
    ),
)


def compilable(code: str, mode: str = "exec") -> bool:
    # This is used as a filter on `from_node()`, but note that LibCST aspires to
    # disallow construction of a CST node which is converted to invalid code.
    # (that is, if the resulting code would be invalid, raise an error instead)
    # See also https://github.com/Instagram/LibCST/issues/287
    try:
        compile(code, "<string>", mode)
        return True
    except SyntaxError:
        return False


def from_node(node: Type[libcst.CSTNode] = libcst.Module) -> st.SearchStrategy[str]:
    assert issubclass(node, libcst.CSTNode)
    return st.from_type(node).map(lambda n: libcst.Module([n]).code).filter(compilable)
