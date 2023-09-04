from __future__ import annotations

from robot.api import logger


def pytest_runtest_teardown():
    logger.error("foo")  # type:ignore[no-untyped-call]
    logger.info("bar")  # type:ignore[no-untyped-call]
