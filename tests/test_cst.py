"""Tests for the hypothesmith.cst module."""
import ast
import dis
from inspect import isabstract
from operator import attrgetter

import hypothesis.strategies as st
import libcst
import pytest
from hypothesis import given, note, target

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


@given(hypothesmith.from_node())
def test_from_node_strategy(code):
    # Use target() to drive towards larger inputs, which are more likely to have bugs
    x = ast.dump(ast.parse(code))
    n_instructions = float(len(list(dis.Bytecode(compile(code, "<string>", "exec")))))
    target(n_instructions, label="number of instructions in bytecode")
    target(float(len(x) - len("Module(body=[])")), label="length of dumped ast body")
