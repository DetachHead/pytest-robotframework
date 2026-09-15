from __future__ import annotations

from pytest import raises
from robot.api import logger

from pytest_robotframework import keyword


@keyword
def asdf():
    logger.info("1")


def test_foo():
    with raises(ZeroDivisionError):  # ruff: ignore[pytest-raises-with-multiple-statements]
        asdf()
        _ = 1 / 0  # ty:ignore[division-by-zero]
