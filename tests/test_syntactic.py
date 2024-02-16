"""Tests for the hypothesmith.syntactic module."""

import ast
import io
import sys
import tokenize

import black
import blib2to3
import parso
import pytest
from hypothesis import example, given, reject, strategies as st

import hypothesmith


def fixup(s):
    """Avoid known issues with tokenize() by editing the string."""
    return "".join(x for x in s if x.isprintable()).strip().strip("\\").strip() + "\n"


@pytest.mark.xfail
@example("#")
@example("\n\\\n")
@example("#\n\x0cpass#\n")
@given(source_code=hypothesmith.from_grammar().map(fixup).filter(str.strip))
def test_tokenize_round_trip_bytes(source_code):
    try:
        source = source_code.encode("utf-8-sig")
    except UnicodeEncodeError:
        reject()
    tokens = list(tokenize.tokenize(io.BytesIO(source).readline))
    outbytes = tokenize.untokenize(tokens)  # may have changed whitespace from source
    output = list(tokenize.tokenize(io.BytesIO(outbytes).readline))
    assert [(t.type, t.string) for t in tokens] == [(t.type, t.string) for t in output]
    # It would be nice if the round-tripped string stabilised.  It doesn't.
    # assert outbytes == tokenize.untokenize(output)


@pytest.mark.xfail
@example("#")
@example("\n\\\n")
@example("#\n\x0cpass#\n")
@given(source_code=hypothesmith.from_grammar().map(fixup).filter(str.strip))
def test_tokenize_round_trip_string(source_code):
    tokens = list(tokenize.generate_tokens(io.StringIO(source_code).readline))
    outstring = tokenize.untokenize(tokens)  # may have changed whitespace from source
    output = tokenize.generate_tokens(io.StringIO(outstring).readline)
    assert [(t.type, t.string) for t in tokens] == [(t.type, t.string) for t in output]
    # It would be nice if the round-tripped string stabilised.  It doesn't.
    # assert outstring == tokenize.untokenize(output)


@pytest.mark.skipif(not hasattr(ast, "unparse"), reason="Can't test before available")
@given(source_code=hypothesmith.from_grammar())
def test_ast_unparse_from_grammar(source_code):
    first = ast.parse(source_code)
    unparsed = ast.unparse(first)
    second = ast.parse(unparsed)
    assert ast.dump(first) == ast.dump(second)


@example("\\", black.Mode())
@example("A#\r#", black.Mode())
@given(
    source_code=hypothesmith.from_grammar(),
    mode=st.builds(
        black.Mode,
        line_length=st.just(88) | st.integers(0, 200),
        string_normalization=st.booleans(),
        is_pyi=st.booleans(),
    ),
)
def test_black_autoformatter_from_grammar(source_code, mode):
    try:
        result = black.format_file_contents(source_code, fast=False, mode=mode)
    except black.NothingChanged:
        pass
    except blib2to3.pgen2.tokenize.TokenError:
        # Fails to tokenise e.g. "\\", though compile("\\", "<string>", "exec") works.
        # See https://github.com/psf/black/issues/1012
        reject()
    except black.InvalidInput:
        # e.g. "A#\r#", see https://github.com/psf/black/issues/970
        reject()
    else:
        with pytest.raises(black.NothingChanged):
            black.format_file_contents(result, fast=False, mode=mode)


@given(source_code=hypothesmith.from_grammar("eval_input"))
def test_eval_input_generation(source_code):
    compile(source_code, filename="<string>", mode="eval")


@given(source_code=hypothesmith.from_grammar(auto_target=False))
def test_generation_without_targeting(source_code):
    compile(source_code, filename="<string>", mode="exec")


@pytest.mark.xfail(sys.version_info >= (3, 13), reason="parso does not support 3.13")
@given(source_code=hypothesmith.from_grammar())
def test_parso_from_grammar(source_code):
    result = parso.parse(source_code).get_code()
    assert source_code == result
