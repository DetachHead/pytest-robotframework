from __future__ import annotations

from pytest_robotframework import AssertOptions


def test_foo():
    left = 1
    right = 1
    assert left == right
    assert right == left, AssertOptions(log_pass=False)
    assert right == right  # noqa: PLR0124
