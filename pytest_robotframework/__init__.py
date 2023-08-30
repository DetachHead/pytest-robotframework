"""useful helpers for you to use in your pytest tests and `conftest.py` files."""

from __future__ import annotations

import inspect
from collections import defaultdict
from functools import wraps
from pathlib import Path

# yes lets put the Callable type in the collection module.... because THAT makes sense!!!
# said no one ever
from typing import TYPE_CHECKING, Callable, ParamSpec, TypeVar  # noqa: UP035

from robot import result, running
from robot.api.interfaces import ListenerV2, ListenerV3
from robot.libraries.BuiltIn import BuiltIn
from robot.running.statusreporter import StatusReporter

from pytest_robotframework._internal.errors import UserError
from pytest_robotframework._internal.robot_utils import execution_context

if TYPE_CHECKING:
    from basedtyping import T

RobotVariables = dict[str, object]

Listener = ListenerV2 | ListenerV3


_suite_variables = defaultdict[Path, RobotVariables](dict)


def set_variables(variables: RobotVariables):
    """sets suite-level variables, equivalent to the `*** Variables ***` section in a `.robot` file.

    also performs some validation checks that robot doesn't to make sure the variable has the
    correct type matching its prefix."""
    suite_path = Path(inspect.stack()[1].filename)
    _suite_variables[suite_path] = variables


_resources = list[Path]()


def import_resource(path: Path | str):
    """imports the specified robot `.resource` file when the suite execution begins.
    use this when specifying robot resource imports at the top of the file.

    to import libraries, use a regular python import"""
    if execution_context():
        BuiltIn().import_resource(str(path))
    else:
        _resources.append(Path(path))


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
            execution_context(),
        ):
            return fn(*args, **kwargs)

    return inner


class _ListenerRegistry:
    def __init__(self):
        self.instances = list[Listener]()
        self.too_late = False


_listeners = _ListenerRegistry()

_T_Listener = TypeVar("_T_Listener", bound=type[Listener])


def listener(cls: _T_Listener) -> _T_Listener:
    """registers a class as a global robot listener. listeners using this decorator are always
    enabled and do not need to be registered with the `--listener` robot option.

    the listener must be defined in a `conftest.py` file so it gets registered before robot starts
    running."""
    if _listeners.too_late:
        raise UserError(
            f"listener {cls.__name__!r} cannot be registered because robot has already"
            " started running. make sure it's defined in a `conftest.py` file"
        )
    _listeners.instances.append(cls())
    return cls
