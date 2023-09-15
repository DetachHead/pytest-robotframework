from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from typing import TYPE_CHECKING, Callable

from robot.api import logger

from pytest_robotframework import keyword

if TYPE_CHECKING:
    from collections.abc import Iterator

    from typing_extensions import assert_type


@keyword
@contextmanager
def asdf() -> Iterator[None]:
    logger.info("start")  # type:ignore[no-untyped-call]
    try:
        yield
    finally:
        logger.info("end")  # type:ignore[no-untyped-call]


# type tests
if TYPE_CHECKING:
    assert_type(asdf, Callable[[], AbstractContextManager[None]])


def test_foo():
    with asdf():
        logger.info(0)  # type:ignore[no-untyped-call]
        raise Exception
    logger.info(1)  # type:ignore[unreachable]
