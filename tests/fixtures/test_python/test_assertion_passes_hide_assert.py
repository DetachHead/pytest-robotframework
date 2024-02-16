from __future__ import annotations

from pytest_robotframework import robot_log


def test_foo():
    left = 1
    right = 1
    assert left == right
    assert right == left, robot_log(show=False)
    assert right == right  # noqa: PLR0124
