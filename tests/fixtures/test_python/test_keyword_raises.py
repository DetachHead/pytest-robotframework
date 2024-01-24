from __future__ import annotations

from robot.api import logger

from pytest_robotframework import keyword


class FooError(Exception):
    pass


@keyword
def bar():
    raise FooError


def test_foo():
    bar()
    logger.info("1")  # pyright:ignore[reportUnreachable]
