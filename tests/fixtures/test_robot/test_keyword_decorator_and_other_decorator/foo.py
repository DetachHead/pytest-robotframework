from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Callable

from robot.api import logger

from pytest_robotframework import keyword

if TYPE_CHECKING:
    from basedtyping import P, T


def decorator(fn: Callable[P, T]) -> Callable[P, T]:
    @wraps(fn)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        return fn(*args, **kwargs)

    return wrapped


@decorator
@keyword
def bar():
    logger.info("1")
