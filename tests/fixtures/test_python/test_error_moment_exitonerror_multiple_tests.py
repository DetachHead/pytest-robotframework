from __future__ import annotations

from robot.api import logger


def test_foo():
    logger.error("foo")  # pyright:ignore[no-untyped-call]
    logger.info("bar")  # pyright:ignore[no-untyped-call]


def test_bar():
    logger.info("baz")  # pyright:ignore[no-untyped-call]
