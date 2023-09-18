from __future__ import annotations

from robot.api import logger

from pytest_robotframework import ignore_failure


def test_foo():
    with ignore_failure():
        logger.info(1 / 0)  # type:ignore[no-untyped-call]
    logger.info(1)  # type:ignore[no-untyped-call]
