"""Tests for the hypothesmith tools."""
import io
import re
import tokenize
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import black
import blib2to3
import hypothesis.strategies as st
import pytest
from hypothesis import HealthCheck, example, given, note, reject, settings

import hypothesmith

settings.register_profile(
    "slow",
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
settings.load_profile("slow")


@pytest.mark.xfail
@example("#")
@example("\n\\\n")
@given(source_code=hypothesmith.from_grammar())
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
@given(source_code=hypothesmith.from_grammar())
def test_tokenize_round_trip_string(source_code):
    tokens = list(tokenize.generate_tokens(io.StringIO(source_code).readline))
    outstring = tokenize.untokenize(tokens)  # may have changed whitespace from source
    output = tokenize.generate_tokens(io.StringIO(outstring).readline)
    assert [(t.type, t.string) for t in tokens] == [(t.type, t.string) for t in output]
    # It would be nice if the round-tripped string stabilised.  It doesn't.
    # assert outstring == tokenize.untokenize(output)


@given(
    source_code=hypothesmith.from_grammar(),
    mode=st.builds(
        black.FileMode,
        line_length=st.just(88) | st.integers(0, 200),
        string_normalization=st.booleans(),
        is_pyi=st.booleans(),
    ),
)
def test_black_autoformatter(source_code, mode):
    note("\n\n#####################################################\n\n")
    note(source_code)
    note("\n------------------------------------------------------\n")
    try:
        note(black.format_str(source_code, mode=mode))
    except blib2to3.pgen2.tokenize.TokenError:
        # Fails to tokenise e.g. "\\", though compile("\\", "<string>", "exec") works.
        # See https://github.com/psf/black/issues/1012
        reject()


@given(source_code=hypothesmith.from_grammar("eval_input"))
def test_eval_input_generation(source_code):
    compile(source_code, filename="<string>", mode="eval")


class Version(NamedTuple):
    major: int
    minor: int
    patch: int

    @classmethod
    def from_string(cls, string):
        return cls(*map(int, string.split(".")))


@lru_cache()
def get_releases():
    pattern = re.compile(r"^### (\d+\.\d+\.\d+) - (\d\d\d\d-\d\d-\d\d)$")
    with open(Path(__file__).parent / "README.md") as f:
        return tuple(
            (Version.from_string(match.group(1)), match.group(2))
            for match in map(pattern.match, f)
            if match is not None
        )


def test_last_release_against_changelog():
    last_version, last_date = get_releases()[0]
    assert last_version == Version.from_string(hypothesmith.__version__)
    assert last_date <= date.today().isoformat()


def test_changelog_is_ordered():
    versions, dates = zip(*get_releases())
    assert versions == tuple(sorted(versions, reverse=True))
    assert dates == tuple(sorted(dates, reverse=True))


def test_version_increments_are_correct():
    # We either increment the patch version by one, increment the minor version
    # and reset the patch, or increment major and reset both minor and patch.
    versions, _ = zip(*get_releases())
    for prev, current in zip(versions[1:], versions):
        assert prev < current  # remember that `versions` is newest-first
        assert current in (
            prev._replace(patch=prev.patch + 1),
            prev._replace(minor=prev.minor + 1, patch=0),
            prev._replace(major=prev.major + 1, minor=0, patch=0),
        ), f"{current} does not follow {prev}"
