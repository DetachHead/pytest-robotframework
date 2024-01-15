from __future__ import annotations

from robot.api import logger


def pytest_runtest_setup():
    logger.error("foo")
    logger.info("bar")
