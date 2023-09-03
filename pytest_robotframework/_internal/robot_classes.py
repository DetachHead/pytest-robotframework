"""robot parsers, prerunmodifiers and listeners that the plugin (`plugin.py`) uses when running
robot (some of them are not activated when running pytest in `--collect-only` mode)"""

from __future__ import annotations

from contextlib import suppress
from types import ModuleType

# callable is not a collection
from typing import (  # noqa: UP035
    TYPE_CHECKING,
    Callable,
    Generator,
    Literal,
    ParamSpec,
    cast,
)

# needed to disable this plugin because we re-implement it
from _pytest import runner  # pylint:disable=import-private-name
from pluggy import HookCaller, HookImpl
from pytest import Function, Item, Session, StashKey
from robot import model, result, running
from robot.api import SuiteVisitor
from robot.api.interfaces import ListenerV3, Parser, TestDefaults
from robot.running.model import Body
from typing_extensions import override

from pytest_robotframework import catch_errors
from pytest_robotframework._internal import robot_library
from pytest_robotframework._internal.errors import InternalError
from pytest_robotframework._internal.robot_utils import Cloaked

if TYPE_CHECKING:
    from pathlib import Path

_P = ParamSpec("_P")


def _create_running_keyword(
    keyword_type: Literal["SETUP", "KEYWORD", "TEARDOWN"],
    fn: Callable[_P, None],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> running.Keyword:
    """creates a `running.Keyword` for the specified keyword from `_robot_library`"""
    if kwargs:
        raise InternalError(f"kwargs not supported: {kwargs}")
    return running.Keyword(
        name=f"{fn.__module__}.{fn.__name__}",
        # robot says this can only be a str but keywords can take any object when called from
        # python
        args=args,  # type:ignore[arg-type]
        type=keyword_type,
    )


collected_robot_suite_key = StashKey[model.TestSuite]()
running_test_case_key = StashKey[running.TestCase]()


def _get_item_from_robot_test(session: Session, test: running.TestCase) -> Item | None:
    try:
        return next(
            item for item in session.items if item.stash[running_test_case_key] == test
        )
    except StopIteration:
        # the robot test was found but got filtered out by pytest
        return None


class PythonParser(Parser):
    """custom robot "parser" for python files. doesn't actually do any parsing, but instead creates
    empty test suites for each python file found by robot. this is required for the prerunmodifiers.
    they do all the work

    the `PytestCollector` prerunmodifier then creates empty test cases for each suite, and
    `PytestRuntestProtocolInjector` inserts the actual test functions which are responsible for
    actually running the setup/call/teardown functions"""

    def __init__(self, session: Session) -> None:
        self.session = session
        super().__init__()

    extension = "py"

    @staticmethod
    def _create_suite(source: Path) -> running.TestSuite:
        return running.TestSuite(
            running.TestSuite.name_from_source(source), source=source
        )

    @override
    def parse(self, source: Path, defaults: TestDefaults) -> running.TestSuite:
        suite = self._create_suite(source)
        # this fake test is required to prevent the suite from being deleted before the
        # prerunmodifiers are called
        test_case = running.TestCase(name="fake test you shoud NEVER see this!!!!!!!")
        test_case.body = [
            _create_running_keyword(
                "KEYWORD",
                robot_library.internal_error,  # type:ignore[no-any-expr]
                Cloaked[str](
                    "fake placeholder test appeared. this should never happen :(("
                ),
            )
        ]
        suite.tests.append(test_case)
        return suite

    @override
    def parse_init(self, source: Path, defaults: TestDefaults) -> running.TestSuite:
        return self._create_suite(source.parent)


@catch_errors
class PytestCollector(SuiteVisitor):
    """
    calls the pytest collection hooks.

    if `collect_only` is `True`, it also removes all suites/tests so that robot doesn't run anything

    if `collect_only` is `False`, it also does the following to prepare the tests for execution:

    - filters out any `.robot` tests/suites that are not included in the collected pytest tests
    - adds the collected `.py` test cases to the robot test suites (with empty bodies. bodies are
    added later by `PytestRuntestProtocolInjector`)
    """

    def __init__(self, session: Session, *, collect_only: bool):
        self.session = session
        self.collect_only = collect_only
        self.collection_error: Exception | None = None

    @override
    def visit_suite(self, suite: running.TestSuite):
        if not suite.parent:  # only do this once, on the top level suite
            self.session.stash[collected_robot_suite_key] = suite
            try:
                self.session.perform_collect()
            except Exception as e:  # noqa: BLE001
                # if collection fails we still need to clean up the suite (ie. delete all the fake
                # tests), so we defer the error to `end_suite` for the top level suite
                self.collection_error = e
            # create robot test cases for python tests:
            for item in self.session.items:
                if (
                    # don't include RobotItems as .robot files are parsed by robot's default parser
                    not isinstance(item, Function)
                ):
                    continue
                test_case = running.TestCase(
                    name=item.name,
                    doc=cast(Function, item.function).__doc__ or "",
                    tags=[
                        ":".join(
                            [
                                marker.name,
                                *(
                                    str(arg)
                                    for arg in cast(tuple[object, ...], marker.args)
                                ),
                            ]
                        )
                        for marker in item.iter_markers()
                    ],
                )
                test_case.body = Body()
                item.stash[running_test_case_key] = test_case
        if self.collect_only:
            suite.tests.clear()  # type:ignore[no-untyped-call]
        else:
            # remove any .robot tests that were filtered out by pytest (and the fake test
            # from `PythonParser`):
            for test in suite.tests[:]:
                if not _get_item_from_robot_test(self.session, test):
                    suite.tests.remove(test)

            # add any .py tests that were collected by pytest
            for item in self.session.items:
                if isinstance(item, Function):
                    module = cast(ModuleType, item.module)
                    if module.__doc__ and not suite.doc:
                        suite.doc = module.__doc__
                    if item.path == suite.source:
                        suite.tests.append(item.stash[running_test_case_key])
        super().visit_suite(suite)

    @override
    def end_suite(self, suite: running.TestSuite):
        """Remove suites that are empty after removing tests."""
        suite.suites = [s for s in suite.suites if s.test_count > 0]
        if not suite.parent and self.collection_error:
            raise self.collection_error


original_setup_key = StashKey[model.Keyword]()
original_body_key = StashKey[Body]()
original_teardown_key = StashKey[model.Keyword]()


@catch_errors
class PytestRuntestProtocolInjector(SuiteVisitor):
    """injects the setup, call and teardown hooks from `_pytest.runner.pytest_runtest_protocol` into
    the robot test suite. this replaces any existing setup/body/teardown with said hooks, which may
    or may not be an issue depending on whether a python or robot test is being run.

    - if running a `.robot` test: the test cases would already have setup/body/teardown keywords, so
    make sure the hooks actually call those keywords (`original_setup_key`, `original_body_key` and
    `original_teardown_key` stashes are used to send the original keywords to the methods on
    `RobotFile`)
    - if running a `.py` test, this is not an issue because the robot test cases are empty (see
    `PythonParser`) and the hook functions already have the actual contents of the tests, because
    they are just plain pytest tests

    since the real life `pytest_runtest_protocol` no longer gets called, none of its hooks get
    called either. calling those hooks is handled by the `PytestRuntestProtocolHooks` listener
    """

    def __init__(self, session: Session):
        self.session = session

    @override
    def start_suite(self, suite: running.TestSuite):
        suite.resource.imports.library(
            robot_library.__name__, alias=robot_library.__name__
        )
        for test in suite.tests:
            item = _get_item_from_robot_test(self.session, test)
            if not item:
                raise InternalError(
                    "this should NEVER happen, `PytestCollector` failed to filter out"
                    f" {test.name}"
                )
            cloaked_item = Cloaked(item)
            item.stash[original_setup_key] = test.setup
            # TODO: whats this mypy error
            #  https://github.com/DetachHead/pytest-robotframework/issues/36
            test.setup = _create_running_keyword(  # type:ignore[assignment]
                "SETUP",
                robot_library.setup,  # type:ignore[no-any-expr]
                cloaked_item,
            )

            item.stash[original_body_key] = test.body  # type:ignore[misc]
            test.body = Body(
                items=[
                    _create_running_keyword(
                        "KEYWORD",
                        robot_library.run_test,  # type:ignore[no-any-expr]
                        cloaked_item,
                    )
                ]
            )

            item.stash[original_teardown_key] = test.teardown
            test.teardown = _create_running_keyword(
                "TEARDOWN",
                robot_library.teardown,  # type:ignore[no-any-expr]
                cloaked_item,
            )


_HookWrapper = Generator[None, object, object]


@catch_errors
class PytestRuntestProtocolHooks(ListenerV3):
    """runs the `pytest_runtest_logstart` and `pytest_runtest_logfinish` hooks from
    `pytest_runtest_protocol`. since all the other parts of `_pytest.runner.runtestprotocol` are
    re-implemented in `PytestRuntestProtocolInjector`.

    also handles the execution of all other `pytest_runtest_protocol` hooks.
    """

    def __init__(self, session: Session):
        self.session = session
        self.original_hookimpls: list[HookImpl] | None = None
        self.stop_running_hooks = False
        self.hookwrappers = dict[HookImpl, _HookWrapper]()
        """hookwrappers that are in the middle of running"""
        self.start_test_hooks = list[HookImpl]()
        self.end_test_hooks = list[HookImpl]()

    def _get_item(self, data: running.TestCase) -> Item:
        item = _get_item_from_robot_test(self.session, data)
        if not item:
            raise InternalError(
                f"failed to find pytest item for robot test: {data.name}"
            )
        return item

    def _get_hookcaller(self) -> HookCaller:
        return cast(
            HookCaller,
            self.session.ihook.pytest_runtest_protocol,  # type:ignore[no-any-expr]
        )

    def _call_hooks(self, item: Item, hookimpls: list[HookImpl]) -> object:
        hook_caller = self._get_hookcaller()
        # can't use the public get_hookimpls method because it returns a copy and we need to mutate
        # the original
        hook_caller._hookimpls[:] = []  # noqa: SLF001
        for hookimpl in hookimpls:
            hook_caller._add_hookimpl(hookimpl)  # noqa: SLF001
        return cast(
            object,
            self._get_hookcaller()(item=item, nextitem=cast(Item, item.nextitem)),
        )

    @override
    def start_suite(
        self,
        data: running.TestSuite,
        result: result.TestSuite,  # pylint:disable=redefined-outer-name
    ):
        if data.parent:
            # only need to do this once, so we only do it for the top level suite
            return
        hook_caller = self._get_hookcaller()

        # remove the runner plugin because `PytestRuntestProtocolInjector` re-implements it
        with suppress(ValueError):  # already been removed
            hook_caller._remove_plugin(runner)  # noqa: SLF001

        def enter_wrapper(hook: HookImpl, item: Item, nextitem: Item) -> object:
            """calls the first half of a hookwrapper"""
            wrapper_generator = cast(
                _HookWrapper,
                hook.function(
                    *(
                        {"item": item, "nextitem": nextitem}[argname]
                        for argname in hook.argnames
                    )
                ),
            )
            self.hookwrappers[hook] = wrapper_generator
            return next(wrapper_generator)

        def exit_wrapper(hook: HookImpl) -> object:
            """calss the second half of a hookwrapper"""
            try:
                next(self.hookwrappers[hook])
            except StopIteration as e:
                return cast(object, e.value)
            raise InternalError(
                f"pytest_runtest_protocol hookwrapper {hook} didn't raise StopIteration"
            )

        all_hooks = hook_caller.get_hookimpls()

        for hook in all_hooks:
            if hook.opts["hookwrapper"]:
                # split the hook wrappers into separate tryfirst and trylast hooks so we can execute
                # them separately
                self.start_test_hooks.append(
                    HookImpl(
                        hook.plugin,
                        hook.plugin_name,
                        lambda item, nextitem, *, hook=hook: enter_wrapper(
                            hook, item, nextitem
                        ),
                        {
                            **hook.opts,
                            "hookwrapper": False,
                            "tryfirst": True,
                            "trylast": False,
                        },
                    )
                )
                self.end_test_hooks.append(
                    HookImpl(
                        hook.plugin,
                        hook.plugin_name,
                        lambda hook=hook: exit_wrapper(hook),
                        {
                            **hook.opts,
                            "hookwrapper": False,
                            "tryfirst": False,
                            "trylast": True,
                        },
                    )
                )
            elif hook.opts["trylast"]:
                self.end_test_hooks.append(hook)
            else:
                self.start_test_hooks.append(hook)

    @override
    def start_test(
        self,
        data: running.TestCase,
        result: result.TestCase,  # pylint:disable=redefined-outer-name
    ):
        item = self._get_item(data)
        if self._call_hooks(item, self.start_test_hooks) is not None:
            # stop on non-None result
            self.stop_running_hooks = True
        item.ihook.pytest_runtest_logstart(  # type:ignore[no-any-expr]
            nodeid=item.nodeid, location=item.location
        )

    @override
    def end_test(
        self,
        data: running.TestCase,
        result: result.TestCase,  # pylint:disable=redefined-outer-name
    ):
        item = self._get_item(data)
        item.ihook.pytest_runtest_logfinish(  # type:ignore[no-any-expr]
            nodeid=item.nodeid, location=item.location
        )
        if self.stop_running_hooks:
            self.stop_running_hooks = False  # for next time
        else:
            self._call_hooks(item, self.end_test_hooks)
