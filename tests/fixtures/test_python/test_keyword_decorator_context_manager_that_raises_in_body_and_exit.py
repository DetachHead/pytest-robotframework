from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from robot.api import logger

from pytest_robotframework import keyword

if TYPE_CHECKING:
    from collections.abc import Iterator


@keyword
@contextmanager
def asdf() -> Iterator[None]:
    logger.info("start")  # type:ignore[no-untyped-call]
    try:
        yield
    finally:
        raise Exception("asdf")


def test_foo():
    with asdf():
        raise Exception("fdsa")
    logger.info(1)  # type:ignore[unreachable]
