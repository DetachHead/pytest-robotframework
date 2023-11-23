from __future__ import annotations

from robot.api.logger import info


def test_foo():
    info("hi")  # type:ignore[no-untyped-call]
