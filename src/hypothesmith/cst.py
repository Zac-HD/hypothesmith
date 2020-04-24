"""
Generating Python source code from a syntax tree.

Thanks to Instagram for open-sourcing libCST (which is great!) and
thanks to Tolkein for the name of this module.
"""
import inspect
import sys
from functools import partial
from tokenize import (  # type: ignore
    Floatnumber as FLOATNUMBER_RE,
    Imagnumber as IMAGNUMBER_RE,
    Intnumber as INTNUMBER_RE,
)
from typing import Callable, Dict, Set, Type, Union, get_type_hints

import hypothesis.strategies as st
import libcst
from hypothesis import infer

from hypothesmith.syntactic import identifiers

# Evil monkeypatching hack because Hypothesis doesn't (yet) know typing_extensions
if hasattr(sys.modules.get("typing_extensions"), "Literal") and not hasattr(
    sys.modules.get("typing"), "Literal"
):
    sys.modules["typing"].Literal = sys.modules["typing_extensions"].Literal


_KNOWN: Set[libcst.CSTNode] = set()

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
    _KNOWN.add(node_type)

# `from_type()` has less laziness than other strategies, we we register for these
# foundational node types *before* referring to them in other strategies.
st.register_type_strategy(libcst.Name, st.builds(libcst.Name, identifiers()))
st.register_type_strategy(
    libcst.SimpleString, st.builds(libcst.SimpleString, st.text().map(repr))
)
_KNOWN |= {libcst.Name, libcst.SimpleString}


def nonempty_seq(node: Type[libcst.CSTNode]) -> st.SearchStrategy:
    return st.lists(st.deferred(lambda: st.from_type(node)), min_size=1)


# There are around 150 concrete types of CST nodes.  Delightfully, libCST uses
# dataclasses for all these classes, so we can allow the `builds` & `from_type`
# inference to provide most of our arguments for us.
# However, in some cases we want to either restrict arguments (e.g. libcst.Name),
# or supply something nastier than the default argument (e.g. libcst.SimpleWhitespace)

NARROW_ARGUMENTS: Dict[Type[libcst.CSTNode], Dict[str, st.SearchStrategy]] = {
    libcst.AsName: {"name": st.from_type(libcst.Name)},
    libcst.Assign: {"targets": nonempty_seq(libcst.AssignTarget)},
    libcst.Comparison: {"comparisons": nonempty_seq(libcst.ComparisonTarget)},
    # libcst.Decorator: {
    #     "decorator": st.from_type(libcst.Name) | st.from_type(libcst.Attribute)
    # },
    libcst.Global: {"names": nonempty_seq(libcst.NameItem)},
    libcst.Import: {"names": nonempty_seq(libcst.ImportAlias)},
    # libcst.ImportFrom: {
    #     "module": st.from_type(libcst.Name) | st.from_type(libcst.Attribute),
    #     "names": nonempty_seq(libcst.ImportAlias),
    # },
    libcst.NamedExpr: {"target": st.from_type(libcst.Name)},
    libcst.Nonlocal: {"names": nonempty_seq(libcst.NameItem)},
    libcst.Set: {
        "elements": nonempty_seq(Union[libcst.Element, libcst.StarredElement])
    },
    libcst.Subscript: {"slice": nonempty_seq(libcst.SubscriptElement)},
    libcst.With: {"items": nonempty_seq(libcst.WithItem)},
}

# We have special handling for `Try` nodes, because there are two options.
# If a Try node has no `except` clause, it *must* have a `finally` clause and
# *must not* have an `else` clause.  With one or more except clauses, it may
# have an else and/or a finally, or neither.  There are also syntactic rules
# governing the handlers, e.g. <=1 bare `except:` clause which must come last.
st.register_type_strategy(
    libcst.Try,
    st.builds(
        libcst.Try,
        handlers=st.lists(
            st.from_type(libcst.ExceptHandler), unique_by=lambda caught: caught.type,
        ),
        orelse=infer,
        finalbody=st.from_type(libcst.Finally),
    )
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


def split_parens(
    node_type: Type[libcst.CSTNode], **kwargs: st.SearchStrategy
) -> libcst.CSTNode:
    # A utility function that splits pairs-of-parens to balanced lists.
    kwargs["lpar"], kwargs["rpar"] = zip(*kwargs.pop("_parens_"))
    return node_type(**kwargs)


def register(node_type: Type[libcst.CSTNode], **strategies: st.SearchStrategy) -> None:
    assert not inspect.isabstract(node_type)
    assert all(isinstance(v, st.SearchStrategy) for v in strategies.values())
    assert node_type is libcst.Try or node_type not in _KNOWN
    target: Callable[..., libcst.CSTNode] = node_type

    hints = get_type_hints(node_type)
    if "lpar" in hints:
        lpar, rpar = hints.pop("lpar").__args__[0], hints.pop("rpar").__args__[0]
        strategies["_parens_"] = st.just(()) | st.lists(
            st.deferred(lambda: st.tuples(st.from_type(lpar), st.from_type(rpar)))
        )
        target = partial(split_parens, node_type)

    for argname, type_ in hints.items():
        if argname not in strategies:
            strategies[argname] = st.deferred(lambda: st.from_type(type_))

    st.register_type_strategy(node_type, st.builds(target, **strategies))


for node_type in tuple(vars(libcst).values()):
    if isinstance(node_type, type) and issubclass(node_type, libcst.CSTNode):
        if inspect.isabstract(node_type):
            # Automatically resolved to union of concrete subclasses
            continue
        if node_type in _KNOWN:
            # Already registered - should be a short list!
            continue
        print(node_type)
        register(node_type, **NARROW_ARGUMENTS.get(node_type, {}))


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
