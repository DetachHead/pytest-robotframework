from __future__ import annotations

from robot.api import logger

from pytest_robotframework import keyword


@keyword(continue_on_failure=True)
def bar():
    logger.info(1 / 0)  # type:ignore[no-untyped-call]


@keyword
def baz():
    logger.info(1)  # type:ignore[no-untyped-call]


def test_foo():
    bar()
    baz()
    logger.info(2)  # type:ignore[no-untyped-call]
