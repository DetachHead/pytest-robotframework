"""useful helpers for you to use in your pytest tests and `conftest.py` files."""

from __future__ import annotations

import inspect
from contextlib import AbstractContextManager, contextmanager, nullcontext
from functools import wraps
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Callable,
    DefaultDict,
    Dict,
    Iterator,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from basedtyping import Function, P, T
from robot import result, running
from robot.api import SuiteVisitor, deco
from robot.api.interfaces import ListenerV2, ListenerV3
from robot.libraries.BuiltIn import BuiltIn
from robot.running.librarykeywordrunner import LibraryKeywordRunner
from robot.running.statusreporter import StatusReporter
from robot.utils import getshortdoc, printable_name
from typing_extensions import override

from pytest_robotframework._internal.cringe_globals import current_item, current_session
from pytest_robotframework._internal.errors import InternalError, UserError
from pytest_robotframework._internal.robot_utils import (
    add_robot_error,
    escape_robot_str,
    execution_context,
)
from pytest_robotframework._internal.utils import ContextManager, patch_method

if TYPE_CHECKING:
    from types import TracebackType

    from robot.running.context import _ExecutionContext


RobotVariables = Dict[str, object]

Listener = Union[ListenerV2, ListenerV3]


_suite_variables = DefaultDict[Path, RobotVariables](dict)


def set_variables(variables: RobotVariables):
    """sets suite-level variables, equivalent to the `*** Variables ***` section in a `.robot` file.

    also performs some validation checks that robot doesn't to make sure the variable has the
    correct type matching its prefix."""
    suite_path = Path(inspect.stack()[1].filename)
    _suite_variables[suite_path] = variables


_resources: list[Path] = []


def import_resource(path: Path | str):
    """imports the specified robot `.resource` file when the suite execution begins.
    use this when specifying robot resource imports at the top of the file.

    to import libraries, use a regular python import"""
    if execution_context():
        BuiltIn().import_resource(escape_robot_str(str(path)))
    else:
        _resources.append(Path(path))


# https://github.com/DetachHead/pytest-robotframework/issues/36
@patch_method(LibraryKeywordRunner)  # type:ignore[arg-type,no-any-decorated,misc]
def _runner_for(
    old_method: Callable[
        [
            LibraryKeywordRunner,
            _ExecutionContext,
            Function,
            list[object],
            dict[str, object],
        ],
        Function,
    ],
    self: LibraryKeywordRunner,
    context: _ExecutionContext,
    handler: Function,
    positional: list[object],
    named: dict[str, object],
) -> Function:
    """use the original function instead of the `@keyword` wrapped one"""
    handler = cast(Function, getattr(handler, "_keyword_original_function", handler))
    return old_method(self, context, handler, positional, named)


class _KeywordDecorator:
    def __init__(
        self,
        *,
        name: str | None = None,
        tags: tuple[str, ...] | None = None,
        module: str | None = None,
        doc: str | None = None,
    ) -> None:
        self.name = name
        self.tags = tags or ()
        self.module = module
        self.doc = doc

    @overload
    def __call__(
        self, fn: Callable[P, AbstractContextManager[T]]
    ) -> Callable[P, AbstractContextManager[T]]: ...

    @overload
    def __call__(self, fn: Callable[P, T]) -> Callable[P, T]: ...

    def __call__(self, fn: Callable[P, T]) -> Callable[P, T]:
        if isinstance(fn, _KeywordDecorator):
            return fn  # type:ignore[unreachable]
        keyword_name = self.name or cast(
            str,
            printable_name(  # type:ignore[no-untyped-call]
                fn.__name__, code_style=True
            ),
        )
        # this doesn't really do anything in python land but we call the original robot keyword
        # decorator for completeness
        deco.keyword(name=keyword_name, tags=self.tags)(fn)

        def create_status_reporter(
            *args: P.args, **kwargs: P.kwargs
        ) -> AbstractContextManager[None]:
            if self.module is None:
                self.module = fn.__module__
            log_args = (
                *(str(arg) for arg in args),
                *(f"{key}={value}" for key, value in kwargs.items()),
            )
            context = execution_context()
            return (
                StatusReporter(
                    running.Keyword(name=keyword_name, args=log_args),
                    result.Keyword(
                        kwname=keyword_name,
                        libname=self.module,
                        doc=(
                            (
                                getshortdoc(  # type:ignore[no-untyped-call,no-any-expr]
                                    inspect.getdoc(fn)
                                )
                                or ""
                            )
                            if self.doc is None
                            else self.doc
                        ),
                        args=log_args,
                        tags=self.tags,
                    ),
                    context=context,
                    # we suppress the error in the status reporter because we raise it ourselves
                    # afterwards, so that context managers like `pytest.raises` can see the actual
                    # exception instead of `robot.errors.HandlerExecutionFailed`
                    suppress=True,
                )
                if context
                else nullcontext()
            )

        def exit_status_reporter(
            status_reporter: AbstractContextManager[None],
            error: BaseException | None = None,
        ):
            if error is None:
                status_reporter.__exit__(None, None, None)
            else:
                status_reporter.__exit__(type(error), error, error.__traceback__)

        class WrappedContextManager(ContextManager[T]):
            """defers exiting the status reporter until after the wrapped context
            manager is finished"""

            def __init__(
                self,
                wrapped: AbstractContextManager[T],
                status_reporter: AbstractContextManager[None],
            ) -> None:
                self.wrapped = wrapped
                self.status_reporter = status_reporter

            @override
            def __enter__(self) -> T:
                return self.wrapped.__enter__()

            @override
            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc_value: BaseException | None,
                traceback: TracebackType | None,
                /,
            ) -> bool:
                try:
                    suppress = self.wrapped.__exit__(exc_type, exc_value, traceback)
                except BaseException as e:
                    e.__context__ = exc_value
                    exc_value = e
                    suppress = False
                    raise
                finally:
                    exit_status_reporter(
                        self.status_reporter, (None if suppress else exc_value)
                    )
                return suppress or False

        @wraps(fn)
        def inner(*args: P.args, **kwargs: P.kwargs) -> T:
            status_reporter = create_status_reporter(*args, **kwargs)
            status_reporter.__enter__()
            try:
                fn_result = fn(*args, **kwargs)
            # ideally we would only be catching Exception here, but we keywordify some pytest
            # functions that raise Failed, which extends BaseException
            except BaseException as e:
                exit_status_reporter(status_reporter, e)
                raise
            else:
                if isinstance(fn_result, AbstractContextManager):
                    # 🚀 independently verified for safety by the overloads
                    return WrappedContextManager(  # type:ignore[return-value]
                        fn_result, status_reporter
                    )
                exit_status_reporter(status_reporter)
            return fn_result

        inner._keyword_original_function = (  # type:ignore[attr-defined] # noqa: SLF001
            fn
        )
        return inner


@overload
def keyword(
    *,
    name: str | None = ...,
    tags: tuple[str, ...] | None = ...,
    module: str | None = ...,
) -> _KeywordDecorator: ...


@overload
def keyword(
    fn: Callable[P, AbstractContextManager[T]]
) -> Callable[P, AbstractContextManager[T]]: ...


@overload
def keyword(fn: Callable[P, T]) -> Callable[P, T]: ...


def keyword(  # pylint:disable=missing-param-doc
    fn: Callable[P, T] | None = None, *, name=None, tags=None, module=None
):
    """marks a function as a keyword and makes it show in the robot log.

    unlike robot's `deco.keyword` decorator, this one will make your function appear as a keyword in
    the robot log even when ran from a python file.

    if the function returns a context manager, its body is included in the keyword (just make sure
    the `@keyword` decorator is above `@contextmanager`)

    :param name: set a custom name for the keyword in the robot log (default is inferred from the
    decorated function name). equivalent to `robot.api.deco.keyword`'s `name` argument
    :param tags: equivalent to `robot.api.deco.keyword`'s `tags` argument
    :param module: customize the module that appears top the left of the keyword name in the log.
    defaults to the function's actual module
    """
    if fn is None:
        return _KeywordDecorator(name=name, tags=tags, module=module)
    return keyword(name=name, tags=tags, module=module)(fn)


def as_keyword(
    name: str, *, doc="", tags: tuple[str, ...] | None = None
) -> ContextManager[None]:
    """runs the body as a robot keyword.

    example:
    -------
    >>> with as_keyword("do thing"):
    ...     ...

    :param name: the name for the keyword
    :param doc: the documentation to be displayed underneath the keyword in the robot log
    :param tags: tags for the keyword
    on failure` keyword
    """

    @_KeywordDecorator(name=name, tags=tags, doc=doc, module="")
    @contextmanager
    def fn() -> Iterator[None]:
        yield

    return cast(ContextManager[None], fn())


def keywordify(
    obj: object,
    method_name: str,
    *,
    name: str | None = None,
    tags: tuple[str, ...] | None = None,
    module: str | None = None,
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
    :param module: customize the module that appears top the left of the keyword name in the log.
    defaults to the function's actual module
    """
    setattr(
        obj,
        method_name,
        keyword(name=name, tags=tags, module=module)(
            getattr(obj, method_name)  # type:ignore[no-any-expr]
        ),
    )


_T_ListenerOrSuiteVisitor = TypeVar(
    "_T_ListenerOrSuiteVisitor", bound=Type[Union[Listener, SuiteVisitor]]
)


def catch_errors(cls: _T_ListenerOrSuiteVisitor) -> _T_ListenerOrSuiteVisitor:
    """errors that occur inside suite visitors and listeners do not cause the test run to fail. even
    `--exitonerror` doesn't catch every exception (see https://github.com/robotframework/robotframework/issues/4853).

    this decorator will remember any errors that occurred inside listeners and suite visitors, then
    raise them after robot has finished running.

    you don't need this if you registered your listener with the `@listener` decorator, as it
    applies this decorator as well"""

    def wrapped(fn: Callable[P, T]) -> Callable[P, T]:
        @wraps(fn)
        def inner(*args: P.args, **kwargs: P.kwargs) -> T:
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                item_or_session = current_item() or current_session()
                if not item_or_session:
                    raise InternalError(
                        # stack trace isn't showsn so we neewd to include the original error in the
                        # message as well
                        f"an error occurred inside {cls.__name__} and failed to get the"
                        f" current pytest item/session: {e}"
                    ) from e
                add_robot_error(item_or_session, str(e))
                raise

        return inner

    for name, method in inspect.getmembers(
        cls,
        predicate=lambda attr: inspect.isfunction(attr)
        # the wrapper breaks static methods idk why, but we shouldn't need to wrap them anyway
        # because robot listeners/suite visitors don't call any static/class methods
        and not isinstance(
            inspect.getattr_static(cls, attr.__name__),  # type:ignore[no-any-expr]
            (staticmethod, classmethod),
        )
        # only wrap methods that are overwritten on the subclass
        and attr.__name__ in vars(cls)  # type:ignore[no-any-expr]
        # don't wrap private/dunder methods since they'll get called by the public ones and we don't
        # want to duplicate errors
        and not attr.__name__.startswith("_"),
    ):
        setattr(cls, name, wrapped(method))  # type:ignore[no-any-expr]
    return cls


class _ListenerRegistry:
    def __init__(self):
        self.instances: list[Listener] = []
        self.too_late = False


_listeners = _ListenerRegistry()

_T_Listener = TypeVar("_T_Listener", bound=Type[Listener])


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
    _listeners.instances.append(catch_errors(cls)())
    return cls
