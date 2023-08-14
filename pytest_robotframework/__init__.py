import inspect
from collections import defaultdict
from functools import wraps
from pathlib import Path

# yes lets put the Callable type in the collection module.... because THAT makes sense!!! said no one ever
from typing import Callable, Mapping, ParamSpec, cast  # noqa: UP035

from basedtyping import T
from robot import result, running
from robot.libraries.BuiltIn import BuiltIn
from robot.running.context import _ExecutionContext
from robot.running.statusreporter import StatusReporter

RobotVariables = dict[str, list[object]]

_suite_variables = defaultdict[Path, RobotVariables](dict)


def set_variables(variables: dict[str, object]):
    """sets suite-level variables, equivalent to the `*** Variables ***` section in a `.robot` file.

    also performs some validation checks that robot doesn't to make sure the variable has the correct
    type matching its prefix."""
    list_variables = {}
    for key, value in variables.items():
        if key.startswith("$"):
            new_value = [value]
        elif key.startswith("@"):
            if not isinstance(value, list):
                raise TypeError("robot variables prefixed with `@` must be a `list`")
            new_value = value
        elif key.startswith("&"):
            if not isinstance(value, Mapping):
                raise TypeError("robot variables prefixed with `&` must be a `Mapping`")
            new_value = [f"{key}={value}" for value in value.items()]
        else:
            raise Exception(
                f"incorrect format for variable key: `{key}`. variables should start with `$`, `@` or `&`."
                "see https://docs.robotframework.org/docs/variables#when-to-use--and--and--and- for more information"
            )
        list_variables[key] = new_value
    suite_path = Path(inspect.stack()[1].filename)
    _suite_variables[suite_path] = list_variables


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
