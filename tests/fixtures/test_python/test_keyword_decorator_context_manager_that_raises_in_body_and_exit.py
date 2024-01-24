from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from robot.api import logger

from pytest_robotframework import keyword

if TYPE_CHECKING:
    from collections.abc import Iterator


@keyword(wrap_context_manager=True)
@contextmanager
def asdf() -> Iterator[None]:
    logger.info("start")
    try:
        yield
    finally:
        raise Exception("asdf")


def test_foo():
    with asdf():
        raise Exception("fdsa")
    logger.info("1")  # pyright:ignore[reportUnreachable]
