from __future__ import annotations

from robot.api import logger

from pytest_robotframework import as_keyword


class FooError(Exception):
    pass


def test_foo():
    try:
        with as_keyword("hi"):
            raise FooError  # ruff: ignore[raise-within-try]
    except FooError:
        logger.info("2")
