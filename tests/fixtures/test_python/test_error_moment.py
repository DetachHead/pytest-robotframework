from __future__ import annotations

from robot.api import logger


def test_foo():
    logger.error("foo")  # type:ignore[no-untyped-call]
    logger.info("bar")  # type:ignore[no-untyped-call]
