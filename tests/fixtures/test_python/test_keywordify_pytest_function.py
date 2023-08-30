from __future__ import annotations

from pytest import raises
from robot.api import logger


def test_foo():
    with raises(ZeroDivisionError):
        logger.info(1 / 0)  # type:ignore[no-untyped-call]
