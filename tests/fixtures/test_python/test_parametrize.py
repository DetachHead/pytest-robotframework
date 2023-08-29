from __future__ import annotations

from pytest import mark


@mark.parametrize(("test_input", "expected"), [(1, 8), (6, 6)])
def test_eval(test_input: int, expected: int):
    assert test_input == expected
