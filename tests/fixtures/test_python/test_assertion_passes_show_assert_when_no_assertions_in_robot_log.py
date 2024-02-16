from __future__ import annotations

from pytest_robotframework import robot_log


def test_foo():
    left = 1
    right = 1
    assert left == right, robot_log(show=True)
    assert right == left
    assert right == right, robot_log(show=True)  # noqa: PLR0124
