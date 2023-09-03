"""useful helpers for you to use in your pytest tests and `conftest.py` files."""

from __future__ import annotations

import inspect
from collections import defaultdict
from contextlib import AbstractContextManager, contextmanager
from functools import wraps
from pathlib import Path

# yes lets put the Callable type in the collection module.... because THAT makes sense!!!
# said no one ever
from typing import TYPE_CHECKING, Callable, ParamSpec, TypeVar, overload  # noqa: UP035

from black import nullcontext
from robot import result, running
from robot.api import deco
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

_T_ContextManager = TypeVar("_T_ContextManager", bound=AbstractContextManager[object])


@overload
def keyword(
    *, name: str | None = ..., tags: tuple[str, ...] | None = ..., context_manager: True
) -> Callable[[Callable[_P, _T_ContextManager]], Callable[_P, _T_ContextManager]]:
    ...


@overload
def keyword(
    *,
    name: str | None = ...,
    tags: tuple[str, ...] | None = ...,
    context_manager: bool = ...,
) -> Callable[[Callable[_P, T]], Callable[_P, T]]:
    ...


@overload
def keyword(fn: Callable[_P, T]) -> Callable[_P, T]:
    ...


def keyword(  # pylint:disable=missing-param-doc
    fn: Callable[_P, T] | None = None, *, name=None, tags=None, context_manager=False
):
    """marks a function as a keyword and makes it show in the robot log.

    unlike robot's `deco.keyword` decorator, this one will make your function appear
    as a keyword in the robot log even when ran from a python file.

    :param name: set a custom name for the keyword in the robot log (default is inferred from the
    decorated function name). equivalent to `robot.api.deco.keyword`'s `name` argument
    :param tags: equivalent to `robot.api.deco.keyword`'s `tags` argument
    :param context_manager: whether the decorated function is a context manager or not
    """
    if fn is not None:
        return keyword(name=name, tags=tags, context_manager=context_manager)(fn)

    def decorator(fn: Callable[_P, T]) -> Callable[_P, T]:
        if hasattr(fn, "_pytest_robot_keyword"):
            return fn

        # this doesn't really do anything in python land but we call the original robot keyword
        # decorator for completeness
        deco.keyword(name=name, tags=tags)(fn)

        def create_status_reporter(
            *args: _P.args, **kwargs: _P.kwargs
        ) -> AbstractContextManager[None]:
            log_args = (
                *(str(arg) for arg in args),
                *(f"{key}={value}" for key, value in kwargs.items()),
            )
            context = execution_context()
            keyword_name = name or fn.__name__
            return (
                StatusReporter(
                    running.Keyword(name=keyword_name, args=log_args),
                    result.Keyword(
                        kwname=keyword_name,
                        libname=fn.__module__,
                        doc=fn.__doc__ or "",
                        args=log_args,
                        tags=tags or [],
                    ),
                    context=context,
                )
                if context
                else nullcontext()
            )

        if context_manager:

            @contextmanager  # type:ignore[arg-type]
            def inner(*args: _P.args, **kwargs: _P.kwargs) -> T:  # type:ignore[misc]
                with (
                    create_status_reporter(*args, **kwargs),
                    fn(  # type:ignore[attr-defined]
                        *args, **kwargs
                    ) as context_manager_result,
                ):
                    yield context_manager_result

        else:

            @wraps(fn)
            def inner(*args: _P.args, **kwargs: _P.kwargs) -> T:
                with create_status_reporter(*args, **kwargs):
                    return fn(*args, **kwargs)

        inner._pytest_robot_keyword = True  # type:ignore[attr-defined] # noqa: SLF001

        return inner  # type:ignore[return-value]

    return decorator


def keywordify(
    obj: object,
    method_name: str,
    *,
    name: str | None = None,
    tags: tuple[str, ...] | None = None,
    context_manager=False,
):
    """patches a function to make it show as a keyword in the robot log.

    you should only use this on third party modules that you don't control. if you want your own
    function to show as a keyword you should decorate it with `@keyword` instead (the one from this
    module, not the one from robot)

    :param obj: the object with the method to patch on it (this has to be specified separately as
    the object itself needs to be modified with the patched method)
    :param method_name: the name of the method to patch
    :param name: set a custom name for the keyword in the robot log (default is inferred from the
    decorated function name). equivalent to `robot.api.deco.keyword`'s `name` argument
    :param tags: equivalent to `robot.api.deco.keyword`'s `tags` argument
    :param context_manager: whether the patched function is a context manager or not
    """
    setattr(
        obj,
        method_name,
        keyword(name=name, tags=tags, context_manager=context_manager)(
            getattr(obj, method_name)  # type:ignore[no-any-expr]
        ),
    )


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
