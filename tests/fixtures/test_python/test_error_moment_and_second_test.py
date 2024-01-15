from __future__ import annotations

from robot.api import logger


def test_foo():
    logger.error("foo")


def test_bar():
    logger.info("bar")
