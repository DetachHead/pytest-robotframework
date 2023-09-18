from __future__ import annotations

from robot.api import logger

from pytest_robotframework import continue_on_failure


class FooError(Exception):
    pass


def test_foo():
    with continue_on_failure():
        logger.info(1 / 0)  # type:ignore[no-untyped-call]
    raise FooError
