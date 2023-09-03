from __future__ import annotations

from pytest import raises
from robot.api import logger

from pytest_robotframework import keyword


@keyword
def asdf():
    logger.info(1)  # type:ignore[no-untyped-call]


def test_foo():
    with raises(ZeroDivisionError):  # noqa: PT012
        asdf()
        logger.info(1 / 0)  # type:ignore[no-untyped-call]
