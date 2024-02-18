from __future__ import annotations

from robot.api import logger

from pytest_robotframework import keyword


@keyword
def bar():
    logger.info("1")
