from __future__ import annotations

from robot.api import logger


def pytest_runtest_setup():
    logger.error("foo")  # pyright:ignore[no-untyped-call]
    logger.info("bar")  # pyright:ignore[no-untyped-call]
