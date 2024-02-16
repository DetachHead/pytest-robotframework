from __future__ import annotations

from pytest_robotframework import robot_log


def test_foo():
    right = 1
    assert right == "wrong", robot_log(show=False, msg="asdf")
