from functools import wraps

# yes lets put the Callable type in the collection module.... because THAT makes sense!!! said no one ever
from typing import Callable, ParamSpec, cast  # noqa: UP035

from basedtyping import T
from robot import result, running
from robot.libraries.BuiltIn import BuiltIn
from robot.running.context import _ExecutionContext
from robot.running.statusreporter import StatusReporter

_P = ParamSpec("_P")


def keyword(fn: Callable[_P, T]) -> Callable[_P, T]:
    """marks a function as a keyword and makes it show in the robot log.

    unlike robot's `deco.keyword` decorator, this one will make your function appear
    as a keyword in the robot log even when ran from a python file."""

    @wraps(fn)
    def inner(*args: _P.args, **kwargs: _P.kwargs) -> T:
        with StatusReporter(
            running.Keyword(name=fn.__name__),
            result.Keyword(kwname=fn.__name__, doc=fn.__doc__ or ""),
            cast(_ExecutionContext, BuiltIn()._context),
        ):
            return fn(*args, **kwargs)

    return inner
