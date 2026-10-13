from __future__ import annotations

from robot.api import logger

from pytest_robotframework import keyword


class FooError(Exception):
    pass


@keyword  # ty: ignore[deprecated] wrong overload being matched due to https://github.com/astral-sh/ty/issues/128
def bar():
    raise FooError


def test_foo():
    bar()
    logger.info("1")  # pyright:ignore[reportUnreachable] # pyrefly:ignore[unreachable]
