"""Tests for the hypothesmith tools."""

import tokenize

import black
from hypothesis import HealthCheck, Verbosity, given, note, reject, settings

import hypothesmith


@settings(
    deadline=None,
    suppress_health_check=HealthCheck.all(),  # type: ignore
    max_examples=10,
    verbosity=Verbosity.verbose,
)
@given(hypothesmith.from_grammar())
def test_generates_from_syntax(source_code):
    note("\n\n#####################################################\n\n")
    note(source_code)
    note("\n------------------------------------------------------\n")
    try:
        note(black.format_str(source_code, mode=black.FileMode()))
    except (black.InvalidInput, tokenize.TokenError):
        reject()
