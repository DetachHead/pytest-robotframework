from __future__ import annotations

from robot.api import logger


def test_foo():
    logger.error("foo")  # type:ignore[no-untyped-call]


def test_bar():
    logger.info("bar")  # type:ignore[no-untyped-call]
