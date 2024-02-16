from __future__ import annotations

from pytest_robotframework import AssertOptions

show_in_log = AssertOptions(log_pass=True)


def test_foo():
    left = 1
    right = 1
    assert left == right, show_in_log
    assert right == left
    assert right == right, show_in_log  # noqa: PLR0124
