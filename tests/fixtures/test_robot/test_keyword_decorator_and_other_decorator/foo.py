# noqa: INP001
from __future__ import annotations

from functools import wraps

# callable isnt a collection
from typing import TYPE_CHECKING, Callable, ParamSpec  # noqa: UP035

from robot.api import logger

from pytest_robotframework import keyword

if TYPE_CHECKING:
    from basedtyping import T

P = ParamSpec("P")


def decorator(fn: Callable[P, T]) -> Callable[P, T]:
    @wraps(fn)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> T:
        return fn(*args, **kwargs)

    return wrapped


@decorator
@keyword
def bar():
    logger.info(1)  # type:ignore[no-untyped-call]
