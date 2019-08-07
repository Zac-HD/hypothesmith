"""Tests for the hypothesmith tools."""

import black
import hypothesis.strategies as st
from hypothesis import HealthCheck, given, note, settings

import hypothesmith


@settings(deadline=None, suppress_health_check=[HealthCheck.too_slow])
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
    note(black.format_str(source_code, mode=mode))
