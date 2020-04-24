"""Tests for the hypothesmith.cst module."""
import ast
from inspect import isabstract
from operator import attrgetter

import black
import hypothesis.strategies as st
import libcst
import pytest
from hypothesis import given, note

import hypothesmith

NODE_TYPES = frozenset(
    v
    for v in vars(libcst).values()
    if isinstance(v, type) and issubclass(v, libcst.CSTNode) and not isabstract(v)
)


@pytest.mark.parametrize("node", sorted(NODE_TYPES, key=attrgetter("__name__")))
@given(data=st.data())
def test_source_code_from_libcst_node_type(node, data):
    try:
        val = data.draw(st.from_type(node))
    except NameError:
        pytest.skip("NameError, probably a forward reference")
    except TypeError as e:
        if str(e).startswith("super"):
            pytest.skip("something weird here, back later")
        if str(e).startswith("Can't instantiate"):
            pytest.skip("abstract classes somehow leaking into builds()")
        raise
    note(val)
    if not isinstance(val, libcst.Module):
        val = libcst.Module([val])
    try:
        code = val.code
    except libcst._nodes.base.CSTCodegenError:
        pytest.skip("codegen not supported yet, e.g. Annotation")
    note(code)


@pytest.mark.skipif(not hasattr(ast, "unparse"), reason="Can't test before available")
@given(source_code=hypothesmith.from_node())
def test_ast_unparse_from_nodes(source_code):
    first = ast.parse(source_code)
    unparsed = ast.unparse(first)
    second = ast.parse(unparsed)
    assert ast.dump(first) == ast.dump(second)


@given(
    source_code=hypothesmith.from_node(),
    mode=st.builds(
        black.FileMode,
        line_length=st.just(88) | st.integers(0, 200),
        string_normalization=st.booleans(),
        is_pyi=st.booleans(),
    ),
)
def test_black_autoformatter_from_nodes(source_code, mode):
    try:
        black.format_file_contents(source_code, fast=False, mode=mode)
    except black.NothingChanged:
        pass
