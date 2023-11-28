from __future__ import annotations

from robot.api.logger import info

from pytest_robotframework import keyword


@keyword
def bar(arg1: str):
    info(f"{arg1}")  # type:ignore[no-untyped-call]


def test_foo():
    bar(f"hi")
