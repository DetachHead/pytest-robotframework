"""
.. include:: ../README.md

# API
useful helpers for you to use in your pytest tests and `conftest.py` files
"""

from __future__ import annotations

import inspect
from contextlib import AbstractContextManager, contextmanager, nullcontext
from functools import wraps
from pathlib import Path
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Callable,
    ClassVar,
    DefaultDict,
    Dict,
    Iterable,
    Iterator,
    List,
    Mapping,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    overload,
)

from basedtyping import Function, P, T
from pytest import StashKey
from robot import result, running
from robot.api import deco
from robot.api.interfaces import ListenerV2, ListenerV3
from robot.errors import DataError, ExecutionFailed
from robot.libraries.BuiltIn import BuiltIn
from robot.model.visitor import SuiteVisitor
from robot.running.librarykeywordrunner import LibraryKeywordRunner
from robot.running.statusreporter import ExecutionStatus, HandlerExecutionFailed, StatusReporter
from robot.utils import (
    getshortdoc,  # pyright:ignore[reportUnknownVariableType]
    printable_name,  # pyright:ignore[reportUnknownVariableType]
)
from robot.utils.error import ErrorDetails
from typing_extensions import Literal, Never, TypeAlias, deprecated, override

from pytest_robotframework._internal.cringe_globals import current_item, current_session
from pytest_robotframework._internal.errors import InternalError, UserError
from pytest_robotframework._internal.patches.robot import kw_attribute
from pytest_robotframework._internal.robot_utils import (
    Listener as _Listener,
    RobotOptions as _RobotOptions,
    add_robot_error,
    escape_robot_str,
    execution_context,
    is_robot_traceback,
    robot_6,
)
from pytest_robotframework._internal.utils import ClassOrInstance, ContextManager, main_package_name

if TYPE_CHECKING:
    from robot.running.context import _ExecutionContext  # pyright:ignore[reportPrivateUsage]

RobotVariables: TypeAlias = Dict[str, object]
"""variable names and values to be set on the suite level. see the `set_variables` function"""

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
        BuiltIn().import_resource(  # pyright:ignore[reportUnknownMemberType]
            escape_robot_str(str(path))
        )
    else:
        _resources.append(Path(path))


class _FullStackStatusReporter(StatusReporter):
    """Riced status reporter that does the following:

    - inserts the full test traceback into exceptions raisec within it (otherwise it would only go
    back to the start of the keyword, instead of the whole test)
    - does not log failures when they came from a nested keyword, to prevent errors from being
    duplicated for each keyword in the stack"""

    @override
    def _get_failure(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException | None,
        exc_tb: TracebackType,
        context: _ExecutionContext,
    ):
        if exc_value is None:
            return None
        if isinstance(exc_value, ExecutionStatus):
            return exc_value
        if isinstance(exc_value, DataError):
            msg = exc_value.message
            context.fail(msg)  # pyright:ignore[reportUnknownMemberType]
            return ExecutionFailed(msg, syntax=exc_value.syntax)

        tb = None
        full_system_traceback = inspect.stack()
        in_framework = True
        base_tb = exc_tb
        while base_tb and is_robot_traceback(base_tb):
            base_tb = base_tb.tb_next
        for frame in full_system_traceback:
            trace = TracebackType(
                tb or base_tb, frame.frame, frame.frame.f_lasti, frame.frame.f_lineno
            )
            if in_framework and is_robot_traceback(trace):
                continue
            in_framework = False
            tb = trace
            if str(Path(frame.filename)).endswith(
                str(Path(main_package_name) / "_internal/plugin.py")
            ):
                break
        else:
            raise InternalError("erm...")
        exc_value.__traceback__ = tb

        error = ErrorDetails(exc_value)
        failure = HandlerExecutionFailed(error)
        if failure.timeout:
            context.timeout_occurred = True
        # the one we just wrapped. i think this should always be present. maybe we should raise an
        # internal error if it's not, but we don't just to be safe:
        wrapped_errors = _get_status_reporter_failures(exc_value)
        # if the wrapped error has a wrapped error, that means it came from a child keyword and
        # therefore has already been logged by its status reporter
        is_nested_status_reporter_failure = len(wrapped_errors) > 1
        if failure.skip:
            context.skip(error.message)  # pyright:ignore[reportUnknownMemberType]
        elif not is_nested_status_reporter_failure:
            context.fail(error.message)  # pyright:ignore[reportUnknownMemberType]
        if not is_nested_status_reporter_failure and error.traceback:
            context.debug(error.traceback)  # pyright:ignore[reportUnknownMemberType]
        return failure


_status_reporter_exception_attr = "__pytest_robot_status_reporter_exceptions__"


def _get_status_reporter_failures(exception: BaseException) -> list[HandlerExecutionFailed]:
    """normally, robot wraps exceptions from keywords in a `HandlerExecutionFailed` or
    something, but we want to preserve the original exception so that users can use
    `try`/`except` without having to worry about their expected exception being wrapped in
    something else, so instead we just add this attribute to the existing exception so we can
    refer to it after the test is over, to determine if we still need to log the failure or if
    it was already logged inside a keyword

    it's a stack because we need to check if there is more than 1 wrapped exception in
    `FullStackStatusReporter`"""
    wrapped_error: list[HandlerExecutionFailed] | None = getattr(
        exception, _status_reporter_exception_attr, None
    )
    if wrapped_error is None:
        wrapped_error = []
        setattr(exception, _status_reporter_exception_attr, wrapped_error)
    return wrapped_error


class _KeywordDecorator:
    def __init__(
        self,
        *,
        name: str | None = None,
        tags: tuple[str, ...] | None = None,
        module: str | None = None,
        doc: str | None = None,
    ) -> None:
        super().__init__()
        self.name = name
        self.tags = tags or ()
        self.module = module
        self.doc = doc

    @staticmethod
    def _save_status_reporter_failure(exception: BaseException):
        stack = _get_status_reporter_failures(exception)
        stack.append(HandlerExecutionFailed(ErrorDetails(exception)))

    @classmethod
    def inner(
        cls,
        fn: Callable[P, T],
        status_reporter: ContextManager[object],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        error: BaseException | None = None
        with status_reporter:
            try:
                result_ = fn(*args, **kwargs)
            except BaseException as e:
                cls._save_status_reporter_failure(e)
                error = e
                raise
        if error:
            raise error
        # pyright assumes the assignment to error could raise an exception but that will NEVER
        # happen
        return result_  # pyright:ignore[reportReturnType,reportPossiblyUnboundVariable]

    def call(self, fn: Callable[P, T]) -> Callable[P, T]:
        if isinstance(fn, _KeywordDecorator):
            return fn
        keyword_name = self.name or cast(str, printable_name(fn.__name__, code_style=True))
        # this doesn't really do anything in python land but we call the original robot keyword
        # decorator for completeness
        deco.keyword(  # pyright:ignore[reportUnknownMemberType]
            name=keyword_name, tags=self.tags
        )(fn)

        @wraps(fn)
        def inner(*args: P.args, **kwargs: P.kwargs) -> T:
            if self.module is None:
                self.module = fn.__module__
            log_args = (
                *(str(arg) for arg in args),
                *(f"{key}={value!s}" for key, value in kwargs.items()),
            )
            context = execution_context()
            data = running.Keyword(name=keyword_name, args=log_args)
            doc: str = (getshortdoc(inspect.getdoc(fn)) or "") if self.doc is None else self.doc
            # we suppress the error in the status reporter because we raise it ourselves
            # afterwards, so that context managers like `pytest.raises` can see the actual
            # exception instead of `robot.errors.HandlerExecutionFailed`
            suppress = True
            context_manager: ContextManager[
                object
                # nullcontext is typed as returning None which pyright incorrectly marks as
                # unreachable. see ContextManager documentation
            ] = (  # pyright:ignore[reportAssignmentType]
                (
                    # needed to work around pyright bug, see ContextManager documentation
                    _FullStackStatusReporter(
                        data=data,
                        result=(
                            result.Keyword(
                                # pyright is only run when robot 7 is installed
                                kwname=keyword_name,  # pyright:ignore[reportCallIssue]
                                libname=self.module,  # pyright:ignore[reportCallIssue]
                                doc=doc,
                                args=log_args,
                                tags=self.tags,
                            )
                        ),
                        context=context,
                        suppress=suppress,
                    )
                    if robot_6
                    else (
                        _FullStackStatusReporter(
                            data=data,
                            result=result.Keyword(
                                name=keyword_name,
                                owner=self.module,
                                doc=doc,
                                args=log_args,
                                tags=self.tags,
                            ),
                            context=context,
                            suppress=suppress,
                            implementation=cast(
                                LibraryKeywordRunner,
                                context.get_runner(  # pyright:ignore[reportUnknownMemberType]
                                    keyword_name
                                ),
                            ).keyword.bind(data),
                        )
                    )
                )
                if context
                else nullcontext()
            )
            return self.inner(fn, context_manager, *args, **kwargs)

        setattr(inner, kw_attribute, fn)
        return inner


class _FunctionKeywordDecorator(_KeywordDecorator):
    """decorator for a keyword that does not return a context manager. does not allow functions that
    return context managers. if you want to decorate a context manager, pass the
    `wrap_context_manager` argument to the `keyword` decorator"""

    @deprecated(
        "you must explicitly pass `wrap_context_manager` when using `keyword` with a"
        + " context manager"
    )
    @overload
    def __call__(self, fn: Callable[P, AbstractContextManager[T]]) -> Never: ...

    @overload
    def __call__(self, fn: Callable[P, T]) -> Callable[P, T]: ...

    def __call__(self, fn: Callable[P, T]) -> Callable[P, T]:
        return self.call(fn)


_T_ContextManager = TypeVar("_T_ContextManager", bound="AbstractContextManager[object]")


class _NonWrappedContextManagerKeywordDecorator(_KeywordDecorator):
    """decorator for a function that returns a context manager. only wraps the function as a keyword
    but not the body of the context manager it returns. to do that, pass `wrap_context_manager=True`
    """

    def __call__(self, fn: Callable[P, _T_ContextManager]) -> Callable[P, _T_ContextManager]:
        return self.call(fn)


class _WrappedContextManagerKeywordDecorator(_KeywordDecorator):
    """decorator for a function that returns a context manager. only wraps the body of the context
    manager it returns
    """

    @classmethod
    @override
    def inner(
        cls,
        fn: Callable[P, T],
        status_reporter: ContextManager[object],
        /,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        T_WrappedContextManager = TypeVar("T_WrappedContextManager")

        class WrappedContextManager(ContextManager[object]):
            """defers exiting the status reporter until after the wrapped context
            manager is finished"""

            def __init__(
                self,
                wrapped: AbstractContextManager[T_WrappedContextManager],
                status_reporter: ContextManager[object],
            ) -> None:
                super().__init__()
                self.wrapped = wrapped
                self.status_reporter = status_reporter

            @override
            # https://github.com/DetachHead/basedpyright/issues/12
            def __enter__(self) -> object:  # pyright:ignore[reportMissingSuperCall]
                _ = self.status_reporter.__enter__()
                return self.wrapped.__enter__()

            @override
            def __exit__(  # pyright:ignore[reportMissingSuperCall]
                self,
                exc_type: type[BaseException] | None,
                exc_value: BaseException | None,
                traceback: TracebackType | None,
                /,
            ) -> bool:
                suppress = False
                try:
                    suppress = self.wrapped.__exit__(exc_type, exc_value, traceback)
                except BaseException as e:
                    e.__context__ = exc_value
                    exc_value = e
                    raise
                finally:
                    error = None if suppress else exc_value
                    if error is None:
                        _ = self.status_reporter.__exit__(None, None, None)
                    else:
                        cls._save_status_reporter_failure(error)  # pyright:ignore[reportPrivateUsage]
                        _ = self.status_reporter.__exit__(type(error), error, error.__traceback__)
                return suppress or False

        fn_result = fn(*args, **kwargs)
        if not isinstance(fn_result, AbstractContextManager):
            raise TypeError(
                f"keyword decorator expected a context manager but instead got {fn_result!r}"
            )
        # 🚀 independently verified for safety by the overloads
        return WrappedContextManager(  # pyright:ignore[reportReturnType]
            fn_result,  # pyright:ignore[reportUnknownArgumentType]
            status_reporter,
        )

    def __call__(
        self, fn: Callable[P, AbstractContextManager[T]]
    ) -> Callable[P, AbstractContextManager[T]]:
        return self.call(fn)


@overload
def keyword(
    *,
    name: str | None = ...,
    tags: tuple[str, ...] | None = ...,
    module: str | None = ...,
    wrap_context_manager: Literal[True],
) -> _WrappedContextManagerKeywordDecorator: ...


@overload
def keyword(
    *,
    name: str | None = ...,
    tags: tuple[str, ...] | None = ...,
    module: str | None = ...,
    wrap_context_manager: Literal[False],
) -> _NonWrappedContextManagerKeywordDecorator: ...


@overload
def keyword(
    *,
    name: str | None = ...,
    tags: tuple[str, ...] | None = ...,
    module: str | None = ...,
    wrap_context_manager: None = ...,
) -> _FunctionKeywordDecorator: ...


@overload
# prevent functions that return Never from matching the context manager overload
def keyword(  # pyright:ignore[reportOverlappingOverload]
    fn: Callable[P, Never],
) -> Callable[P, Never]: ...


@deprecated(
    "you must explicitly pass `wrap_context_manager` when using `keyword` with a context manager"
)
@overload
def keyword(fn: Callable[P, AbstractContextManager[T]]) -> Never: ...


@overload
def keyword(fn: Callable[P, T]) -> Callable[P, T]: ...


def keyword(  # pylint:disable=missing-param-doc
    fn: Callable[P, T] | None = None,
    *,
    name: str | None = None,
    tags: tuple[str, ...] | None = None,
    module: str | None = None,
    wrap_context_manager: bool | None = None,
) -> _KeywordDecorator | Callable[P, T]:
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
    :param wrap_context_manager: if the decorated function returns a context manager, whether or not
    to wrap the context manager instead of the function. you probably always want this to be `True`,
    unless you don't always intend to use the returned context manager.
    """
    if fn is None:
        if wrap_context_manager is None:
            return _FunctionKeywordDecorator(name=name, tags=tags, module=module)
        if wrap_context_manager:
            return _WrappedContextManagerKeywordDecorator(name=name, tags=tags, module=module)
        return _NonWrappedContextManagerKeywordDecorator(name=name, tags=tags, module=module)
    return keyword(  # pyright:ignore[reportCallIssue,reportUnknownVariableType]
        name=name,
        tags=tags,
        module=module,
        wrap_context_manager=wrap_context_manager,  # pyright:ignore[reportArgumentType]
    )(fn)


def as_keyword(
    name: str,
    *,
    doc: str = "",
    tags: tuple[str, ...] | None = None,
    args: Iterable[str] | None = None,
    kwargs: Mapping[str, str] | None = None,
) -> ContextManager[None]:
    """runs the body as a robot keyword.

    example:
    -------
    >>> with as_keyword("do thing"):
    ...     ...

    :param name: the name for the keyword
    :param doc: the documentation to be displayed underneath the keyword in the robot log
    :param tags: tags for the keyword
    :param args: positional arguments to be displayed on the keyword in the robot log
    :param kwargs: keyword arguments to be displayed on the keyword in the robot log
    """

    @_WrappedContextManagerKeywordDecorator(name=name, tags=tags, doc=doc, module="")
    @contextmanager
    def fn(*_args: str, **_kwargs: str) -> Iterator[None]:
        yield

    return cast(ContextManager[None], fn(*(args or []), **(kwargs or {})))


def keywordify(
    obj: object,
    method_name: str,
    *,
    name: str | None = None,
    tags: tuple[str, ...] | None = None,
    module: str | None = None,
    wrap_context_manager: bool = False,
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
    :param wrap_context_manager: if the decorated function returns a context manager, whether or not
    to wrap the context manager instead of the function. you probably always want this to be `True`,
    unless you don't always intend to use the returned context manager
    """
    setattr(
        obj,
        method_name,
        keyword(  # pyright:ignore[reportCallIssue]
            name=name,
            tags=tags,
            module=module,
            wrap_context_manager=wrap_context_manager,  # pyright:ignore[reportArgumentType]
        )(getattr(obj, method_name)),
    )


_T_ListenerOrSuiteVisitor = TypeVar(
    "_T_ListenerOrSuiteVisitor", bound=Type[Union["Listener", SuiteVisitor]]
)


def catch_errors(cls: _T_ListenerOrSuiteVisitor) -> _T_ListenerOrSuiteVisitor:
    """errors that occur inside suite visitors and listeners do not cause the test run to fail. even
    `--exitonerror` doesn't catch every exception (see <https://github.com/robotframework/robotframework/issues/4853>).

    this decorator will remember any errors that occurred inside listeners and suite visitors, then
    raise them after robot has finished running.

    you don't need this if you are using the `listener` or `pre_rebot_modifier` decorator, as
    those decorators use `catch_errors` as well"""
    # prevent classes from being wrapped twice
    marker = "_catch_errors"
    if hasattr(cls, marker):
        return cls

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
                        + f" current pytest item/session: {e}"
                    ) from e
                add_robot_error(item_or_session, str(e))
                raise

        return inner

    for name, method in cast(
        List[Tuple[str, Function]],
        inspect.getmembers(
            cls,
            predicate=lambda attr: inspect.isfunction(attr)  # pyright:ignore[reportAny]
            # the wrapper breaks static methods idk why, but we shouldn't need to wrap them anyway
            # because robot listeners/suite visitors don't call any static/class methods
            and not isinstance(
                inspect.getattr_static(cls, attr.__name__), (staticmethod, classmethod)
            )
            # only wrap methods that are overwritten on the subclass
            and attr.__name__ in vars(cls)
            # don't wrap private/dunder methods since they'll get called by the public ones and we
            # don't want to duplicate errors
            and not attr.__name__.startswith("_"),
        ),
    ):
        setattr(cls, name, wrapped(method))
    setattr(cls, marker, True)
    return cls


class _RobotClassRegistry:
    listeners: ClassVar[list[Listener]] = []
    pre_rebot_modifiers: ClassVar[list[SuiteVisitor]] = []
    too_late: ClassVar[bool] = False

    @classmethod
    def check_too_late(cls, obj: ClassOrInstance[Listener | SuiteVisitor]):
        if cls.too_late:
            raise UserError(
                f"{(obj if isinstance(obj, type) else type(obj)).__name__} cannot be"
                + " registered because robot has already started running. make sure it's"
                + " defined in a `conftest.py` file"
            )


_T_Listener = TypeVar("_T_Listener", bound=ClassOrInstance["Listener"])


@deprecated(
    "add listeners using the `pytest_robot_modify_options` hook instead. see"
    + " https://github.com/DetachHead/pytest-robotframework#pytest_robot_modify_options-hook"
)
def listener(obj: _T_Listener) -> _T_Listener:
    """registers a class or instance as a global robot listener. listeners using this decorator are
    always enabled and do not need to be registered with the `--listener` robot option.

    must be called before robot starts running (eg. in a `pytest_sessionstart` hook). if using as a
    decorator, the listener must be defined in your `conftest.py` (or in a module imported by it) so
    it gets registered before robot starts running."""
    _RobotClassRegistry.check_too_late(obj)
    _RobotClassRegistry.listeners.append(
        obj if isinstance(obj, (ListenerV2, ListenerV3)) else catch_errors(obj)()
    )
    return obj


_T_SuiteVisitor = TypeVar("_T_SuiteVisitor", bound=ClassOrInstance[SuiteVisitor])


@deprecated(
    "add pre-rebot modifiers using the `pytest_robot_modify_options` hook instead. see"
    + " https://github.com/DetachHead/pytest-robotframework#pytest_robot_modify_options-hook"
)
def pre_rebot_modifier(obj: _T_SuiteVisitor) -> _T_SuiteVisitor:
    """registers a suite visitor as a pre-rebot modifier. classes using this decorator are always
    enabled and do not need to be registered with the `--prerebotmodifier` robot option.

    must be called before robot starts running (eg. in a `pytest_sessionstart` hook). if using as a
    decorator, the class must be defined in your `conftest.py` (or in a module imported by it) so
    it gets registered before robot starts running."""
    _RobotClassRegistry.check_too_late(obj)
    _RobotClassRegistry.pre_rebot_modifiers.append(
        obj if isinstance(obj, SuiteVisitor) else catch_errors(obj)()
    )
    return obj


class AssertOptions:
    """pass this as the second argument to an `assert` statement to customize how it appears in the
    robot log.

    example:
    -------
    .. code-block:: python

        assert foo == bar, AssertOptions(
            log_pass=False, description="checking the value", fail_msg="assertion failed"
        )
    """

    def __init__(
        self,
        *,
        log_pass: bool | None = None,
        description: str | None = None,
        fail_message: str | None = None,
    ) -> None:
        super().__init__()
        self.log_pass = log_pass
        """whether to display the assertion as a keyword in the robot log when it passes.

        by default, a passing `assert` statement will display in the robot log as long as the
        following conditions are met:
        - the `enable_assertion_pass_hook` pytest option is enabled
        - it is not inside a `hide_asserts_from_robot_log` context manager
        (see [enabling pytest assertions in the robot log](https://github.com/DetachHead/pytest-robotframework/#enabling-pytest-assertions-in-the-robot-log)).
        - pytest is not run with the `--no-asserts-in-robot-log` argument

        failing `assert` statements will show as keywords in the log as long as the
        `enable_assertion_pass_hook` pytest option is enabled. if it's disabled, the assertion error
        will be logged, but not within a keyword.

        example:
        -------
        .. code-block:: python

            # (assuming all of these assertions pass)

            # never displays in the robot log:
            assert foo == bar, AssertOptions(log_pass=False)

            # always displays in the robot log (as long as the `enable_assertion_pass_hook` pytest
            # option is enabled):
            assert foo == bar, AssertOptions(log_pass=True)

            # displays in the robot log as only if all 3 conditions mentioned above are met:
            assert foo == bar
        """

        self.description = description
        """normally, the asserted expression as it was written is displayed as the argument to the
        `assert` keyword in the robot log, but setting this value will display a custom message
        instead. when a custom description is used, the original expression is logged inside the
        keyword instead."""

        self.fail_message = fail_message
        """optional description for the `assert` statement that will be included in the
        `AssertionError` message if the assertion fails. equivalent to a normal `assert` statement's
        second argument"""

    @override
    def __repr__(self) -> str:
        """make the custom fail message appear in the call to `AssertionError`"""
        return self.fail_message or ""


_hide_asserts_context_manager_key = StashKey[bool]()


@contextmanager
def hide_asserts_from_robot_log() -> Iterator[None]:
    """context manager for hiding multiple passing `assert` statements from the robot log. note that
    individual `assert` statements using `AssertOptions(log_pass=True)` take precedence, and that
    failing assertions will always appear in the log.

    when hiding only a single `assert` statement, you should use `AssertOptions(log=False)` instead.

    example:
    -------
    .. code-block:: python

        assert True # not hidden
        with hide_asserts_from_robot_log():
            assert True # hidden
            assert True, AssertOptions(log_pass=True) # not hidden
    """
    item = current_item()
    if not item:
        raise InternalError(
            f"failed to get current pytest item in {hide_asserts_from_robot_log.__name__}"
        )
    previous_value = item.stash.get(_hide_asserts_context_manager_key, False)
    item.stash[_hide_asserts_context_manager_key] = True
    try:
        yield
    finally:
        item.stash[_hide_asserts_context_manager_key] = previous_value


# ideally these would just use an explicit re-export
# https://github.com/mitmproxy/pdoc/issues/667
Listener: TypeAlias = _Listener

RobotOptions: TypeAlias = _RobotOptions
"""robot command-line arguments after being parsed by robot into a `dict`.

for example, the following robot options:

```dotenv
ROBOT_OPTIONS="--listener Foo --listener Bar -d baz"
```

will be converted to a `dict` like so:
>>> {"listener": ["Foo", "Bar"], "outputdir": "baz"}

any options missing from this `TypedDict` are not allowed to be modified as they interfere with the
functionality of this plugin. see https://github.com/detachhead/pytest-robotframework#config for
alternatives
"""
