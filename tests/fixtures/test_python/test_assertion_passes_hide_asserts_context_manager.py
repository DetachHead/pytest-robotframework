from __future__ import annotations

from pytest_robotframework import AssertOptions, hide_asserts_from_robot_log


def test_foo():
    left = 1
    right = 1
    assert 1
    with hide_asserts_from_robot_log():
        assert left == right
        assert right == left, AssertOptions(log_pass=True)
        assert right == right  # noqa: PLR0124
    assert 2
