from __future__ import annotations

from robot.api import logger


def pytest_runtest_setup():
    logger.info(2)  # pyright:ignore[no-untyped-call]
