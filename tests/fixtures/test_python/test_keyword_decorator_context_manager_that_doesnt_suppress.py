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
    logger.info("start")  # pyright:ignore[no-untyped-call]
    try:
        yield
    finally:
        logger.info("end")  # pyright:ignore[no-untyped-call]


def test_foo():
    with asdf():
        logger.info(0)  # pyright:ignore[no-untyped-call]
        raise Exception
    logger.info(1)  # pyright:ignore[unreachable]
