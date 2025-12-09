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
    raise Exception("asdf")
    # even though this is unreachable, the yield statement is still needed to make the function a
    # generator for the `contextmanager` decorator to work correctly
    yield  # pyright: ignore[reportUnreachable]


def test_foo():
    with asdf():
        logger.info("0")
    logger.info("1")
