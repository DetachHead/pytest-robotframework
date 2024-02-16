from __future__ import annotations

from pytest_robotframework import AssertOptions


def test_foo():
    right = 1
    assert right == "wrong", AssertOptions(log_pass=False, description="asdf")
