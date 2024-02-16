from __future__ import annotations

from pytest import raises

from pytest_robotframework import AssertOptions


def test_foo():
    left = 1
    right = 1
    assert left == right, "doesn't appear"
    assert right == left, AssertOptions(description="does appear1")
    with raises(AssertionError):
        assert right == "wrong", AssertOptions(log_pass=True, fail_message="does appear2")
    assert right == "wrong", "does appear3"
