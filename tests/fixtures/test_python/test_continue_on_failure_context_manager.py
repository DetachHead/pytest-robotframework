from __future__ import annotations

from robot.api import logger

from pytest_robotframework import continue_on_failure


def test_foo():
    with continue_on_failure() as result:
        logger.info(1 / 0)  # type:ignore[no-untyped-call]
    logger.info(1)  # type:ignore[no-untyped-call]
    assert isinstance(result.value, ZeroDivisionError)
