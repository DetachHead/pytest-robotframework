from __future__ import annotations

from robot.api import logger

from pytest_robotframework import keyword


class FooError(Exception):
    pass


@keyword
def bar():
    raise FooError


def test_foo():
    try:
        bar()
    except FooError:
        logger.info("hi")
