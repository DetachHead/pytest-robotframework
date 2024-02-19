"""robot parsers, prerunmodifiers and listeners that the plugin (`plugin.py`) uses when running
robot (some of them are not activated when running pytest in `--collect-only` mode)"""

from __future__ import annotations

from contextlib import suppress
from re import sub
from types import ModuleType
from typing import TYPE_CHECKING, Callable, Generator, Literal, Optional, Tuple, cast

from _pytest import runner
from ansi2html import Ansi2HTMLConverter
from pluggy import HookImpl
from pluggy._hooks import _SubsetHookCaller  # pyright:ignore[reportPrivateUsage]
from pytest import Function, Item, Session, version_tuple as pytest_version
from robot import model, result, running
from robot.api.interfaces import ListenerV3, Parser
from robot.model import Message, SuiteVisitor
from robot.running.model import Body
from typing_extensions import override

from pytest_robotframework import catch_errors
from pytest_robotframework._internal import robot_library
from pytest_robotframework._internal.errors import InternalError
from pytest_robotframework._internal.pytest_robot_items import (
    RobotItem,
    collected_robot_suite_key,
    original_body_key,
    original_setup_key,
    original_teardown_key,
)
from pytest_robotframework._internal.robot_utils import (
    Cloaked,
    ModelTestSuite,
    add_robot_error,
    full_test_name,
    get_item_from_robot_test,
    running_test_case_key,
)

if TYPE_CHECKING:
    from pathlib import Path

    from basedtyping import P
    from robot.running.builder.settings import TestDefaults


def _create_running_keyword(
    keyword_type: Literal["SETUP", "KEYWORD", "TEARDOWN"],
    fn: Callable[P, None],
    *args: P.args,
    **kwargs: P.kwargs,
) -> running.Keyword:
    """creates a `running.Keyword` for the specified keyword from `_robot_library`"""
    if kwargs:
        raise InternalError(f"kwargs not supported: {kwargs}")
    return running.Keyword(name=f"{fn.__module__}.{fn.__name__}", args=args, type=keyword_type)


_fake_test_tag = "_pytest_robotframework_fake_test"


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
        return running.TestSuite(running.TestSuite.name_from_source(source), source=source)

    @override
    def parse(self, source: Path, defaults: TestDefaults) -> running.TestSuite:
        suite = self._create_suite(source)
        # this fake test is required to prevent the suite from being deleted before the
        # prerunmodifiers are called
        test_case = running.TestCase(
            name="fake test you shoud NEVER see this!!!!!!!", tags=(_fake_test_tag,)
        )
        test_case.body = [
            _create_running_keyword(
                "KEYWORD",
                robot_library.internal_error,
                Cloaked[str]("fake placeholder test appeared. this should never happen :(("),
            )
        ]
        _ = suite.tests.append(test_case)
        return suite

    @override
    def parse_init(self, source: Path, defaults: TestDefaults) -> running.TestSuite:
        return self._create_suite(source.parent)


class _NotRunningTestSuiteError(InternalError):
    def __init__(self) -> None:
        super().__init__(
            "SuiteVisitor should have had a `running.TestSuite` but had a `model.TestSuite` instead"
        )


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

    def __init__(self, session: Session, *, collect_only: bool, item: Item | None = None):
        super().__init__()
        self.session = session
        self.collect_only = collect_only
        self._item = item
        self.xdist_run = item is not None
        self.collection_error: Exception | None = None

    def items(self):
        return [self._item] if self._item else self.session.items

    @override
    # https://github.com/robotframework/robotframework/issues/4940
    def visit_test(  # pyright:ignore[reportIncompatibleMethodOverride]
        self, test: running.TestCase
    ):
        for item in self.items():
            if isinstance(item, RobotItem) and full_test_name(test) == full_test_name(
                item.collected_robot_test
            ):
                # associate .robot test with its pytest item
                item.stash[running_test_case_key] = test

    @override
    def visit_suite(self, suite: ModelTestSuite):
        # https://github.com/robotframework/robotframework/issues/4940
        if not isinstance(suite, running.TestSuite):
            raise _NotRunningTestSuiteError
        if not suite.parent:  # only do this once, on the top level suite
            self.session.stash[collected_robot_suite_key] = suite
            # on pytest <8, if collection has already happened, collecting again will result in an
            # empty list so we can only collect once. on pytest >8, the items attribute is always
            # present. although that makes it safer to double-collect, it will remake all the
            # collected items meaning anything added to their stash will be lost
            if not self.xdist_run and (
                not hasattr(self.session, "items") or (pytest_version >= (8, 0, 0))
            ):
                try:
                    _ = self.session.perform_collect()
                except Exception as e:  # noqa: BLE001
                    # if collection fails we still need to clean up the suite (ie. delete all the
                    # fake tests), so we defer the error to `end_suite` for the top level suite
                    self.collection_error = e
        if not suite.source:
            return
        # save the resolved paths for performance reasons
        if not suite.source.is_absolute():
            suite.source = suite.source.resolve()
        for item in self.items():
            if not item.path.is_absolute():
                item.path = item.path.resolve()
            # only include items that are part of this current suite
            if item.path != suite.source or not isinstance(item, Function):
                continue
            # create robot test case for .py test:
            test_case = running.TestCase(
                name=item.name,
                doc=cast(
                    Function,
                    item.function,  # pyright:ignore[reportUnknownMemberType]
                ).__doc__
                or "",
                tags=[
                    ":".join([
                        marker.name,
                        *(str(arg) for arg in cast(Tuple[object, ...], marker.args)),
                    ])
                    for marker in item.iter_markers()
                ],
                parent=suite,
            )
            test_case.body = Body()
            item.stash[running_test_case_key] = test_case
            module = cast(ModuleType, item.module)
            if module.__doc__ and not suite.doc:
                suite.doc = module.__doc__
            _ = suite.tests.append(test_case)
        # remove the fake placeholder test (there should only ever be 1 fake test):
        fake_tests = [test for test in suite.tests if _fake_test_tag in test.tags]
        if fake_tests:
            # there should never be more than 1 fake test per suite
            (test,) = fake_tests
            suite.tests.remove(test)
        if self.collect_only:
            suite.tests.clear()
        # https://github.com/robotframework/robotframework/issues/4940
        super().visit_suite(suite)  # pyright:ignore[reportUnknownMemberType]

    @override
    def end_suite(self, suite: ModelTestSuite):
        # https://github.com/robotframework/robotframework/issues/4940
        if not isinstance(suite, running.TestSuite):
            raise _NotRunningTestSuiteError

        # remove any .robot tests that were filtered out by pytest (and the fake test from
        # `PythonParser`). we do this in end_suite because that's when all the
        # running_test_case_keys should be populated:
        for test in suite.tests[:]:
            if not get_item_from_robot_test(self.session, test, all_items_should_have_tests=False):
                suite.tests.remove(test)

        # delete any suites that are now empty:
        suite.suites = [s for s in suite.suites if s.test_count > 0]
        # if collection failed, raise the exception now:
        if not suite.parent and self.collection_error:
            raise self.collection_error


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

    unless running with xdist, the real life `pytest_runtest_protocol` no longer gets called, so
    none of its hooks get called either. calling those hooks is handled by the
    `PytestRuntestProtocolHooks` listener
    """

    def __init__(self, *, session: Session, item: Item | None = None):
        super().__init__()
        self.session = session
        self.item = item

    @override
    def start_suite(self, suite: ModelTestSuite):
        if not isinstance(suite, running.TestSuite):
            raise _NotRunningTestSuiteError
        _ = suite.resource.imports.library(robot_library.__name__, alias=robot_library.__name__)
        item: Item | None = None
        for test in suite.tests:
            if self.item:
                item = self.item
            else:
                previous_item: Item | None = item
                item = get_item_from_robot_test(self.session, test)
                if not item:
                    raise InternalError(
                        "this should NEVER happen, `PytestCollector` failed to filter out "
                        + test.name
                    )
                # need to set nextitem on all the items, because for some reason the attribute
                # exists on the class but is never used
                if previous_item and not cast(Optional[Item], previous_item.nextitem):
                    previous_item.nextitem = (  # pyright:ignore[reportAttributeAccessIssue]
                        item
                    )
            cloaked_item = Cloaked(item)
            item.stash[original_setup_key] = test.setup
            test.setup = _create_running_keyword("SETUP", robot_library.setup, cloaked_item)

            item.stash[original_body_key] = test.body
            test.body = Body(
                items=[_create_running_keyword("KEYWORD", robot_library.run_test, cloaked_item)]
            )

            item.stash[original_teardown_key] = test.teardown
            test.teardown = _create_running_keyword(
                "TEARDOWN", robot_library.teardown, cloaked_item
            )


_HookWrapper = Generator[None, object, object]


@catch_errors
class PytestRuntestProtocolHooks(ListenerV3):
    """runs the `pytest_runtest_logstart` and `pytest_runtest_logfinish` hooks from
    `pytest_runtest_protocol`. since all the other parts of `_pytest.runner.runtestprotocol` are
    re-implemented in `PytestRuntestProtocolInjector`.

    also handles the execution of all other `pytest_runtest_protocol` hooks.

    NOT used if running with xdist - in this case `pytest_runtest_protocol` hooks are called
    normally so this listener is not required.
    """

    def __init__(self, session: Session):
        super().__init__()
        self.session = session
        self.stop_running_hooks = False
        self.hookwrappers: dict[HookImpl, _HookWrapper] = {}
        """hookwrappers that are in the middle of running"""
        self.start_test_hooks: list[HookImpl] = []
        self.end_test_hooks: list[HookImpl] = []

    def _get_item(self, data: running.TestCase) -> Item:
        item = get_item_from_robot_test(self.session, data)
        if not item:
            raise InternalError(f"failed to find pytest item for robot test: {data.name}")
        return item

    @staticmethod
    def _call_hooks(item: Item, hookimpls: list[HookImpl]) -> object:
        hook_caller = item.ihook.pytest_runtest_protocol
        original_hookimpls = hook_caller.get_hookimpls()
        try:
            # can't use the public get_hookimpls method because it returns a copy and we need to
            # mutate the original
            hook_caller._hookimpls[:] = []  # pyright:ignore[reportPrivateUsage]
            for hookimpl in hookimpls:
                hook_caller._add_hookimpl(  # pyright:ignore[reportPrivateUsage]
                    hookimpl
                )
            hook_result = cast(
                object, hook_caller(item=item, nextitem=cast(Optional[Item], item.nextitem))
            )
        finally:
            hook_caller._hookimpls[:] = (  # pyright:ignore[reportPrivateUsage]
                original_hookimpls
            )
        return hook_result

    @override
    def start_test(
        self,
        data: running.TestCase,
        result: result.TestCase,  # pylint:disable=redefined-outer-name
    ):
        # setup hooks for the test:
        item = self._get_item(data)
        hook_caller = item.ihook.pytest_runtest_protocol

        # remove the runner plugin because `PytestRuntestProtocolInjector` re-implements it
        original_hook_caller = (
            # need to bypass the _SubsetHookCaller proxy otherwise it won't actually remove the
            # plugin
            hook_caller._orig  # pyright:ignore[reportPrivateUsage]
            if isinstance(hook_caller, _SubsetHookCaller)
            else hook_caller
        )
        with suppress(ValueError):  # already been removed
            original_hook_caller._remove_plugin(  # pyright:ignore[reportPrivateUsage]
                runner
            )

        def enter_wrapper(hook: HookImpl, item: Item, nextitem: Item):
            """calls the first half of a hookwrapper"""
            wrapper_generator = cast(
                _HookWrapper,
                hook.function(
                    *({"item": item, "nextitem": nextitem}[argname] for argname in hook.argnames)
                ),
            )
            self.hookwrappers[hook] = wrapper_generator
            # pretty sure these only ever return `None` but we return it either way just to be safe
            return next(wrapper_generator)

        def exit_wrapper(hook: HookImpl) -> object:
            """calss the second half of a hookwrapper"""
            try:
                next(self.hookwrappers[hook])
            except StopIteration as e:
                # https://github.com/DetachHead/basedpyright/issues/84
                return cast(object, e.value)  # pyright:ignore[reportAny]
            raise InternalError(
                f"pytest_runtest_protocol hookwrapper {hook} didn't raise StopIteration"
            )

        all_hooks = hook_caller.get_hookimpls()

        for hook in all_hooks:
            if hook.opts["hookwrapper"] or hook.opts["wrapper"]:
                # split the hook wrappers into separate tryfirst and trylast hooks so we can execute
                # them separately
                self.start_test_hooks.append(
                    HookImpl(
                        hook.plugin,
                        hook.plugin_name,
                        lambda item, nextitem, *, hook=hook: enter_wrapper(  # pyright:ignore[reportUnknownArgumentType,reportUnknownLambdaType]
                            hook,
                            item,  # pyright:ignore[reportUnknownArgumentType]
                            nextitem,  # pyright:ignore[reportUnknownArgumentType]
                        ),
                        {
                            **hook.opts,
                            "hookwrapper": False,
                            "wrapper": False,
                            "tryfirst": True,
                            "trylast": False,
                        },
                    )
                )
                self.end_test_hooks.append(
                    HookImpl(
                        hook.plugin,
                        hook.plugin_name,
                        lambda hook=hook: exit_wrapper(  # pyright:ignore[reportUnknownArgumentType,reportUnknownLambdaType]
                            hook  # pyright:ignore[reportUnknownArgumentType]
                        ),
                        {
                            **hook.opts,
                            "hookwrapper": False,
                            "wrapper": False,
                            "tryfirst": False,
                            "trylast": True,
                        },
                    )
                )
            elif hook.opts["trylast"]:
                self.end_test_hooks.append(hook)
            else:
                self.start_test_hooks.append(hook)

        # call start test hooks and start hookwrappers:
        if self._call_hooks(item, self.start_test_hooks) is not None:
            # stop on non-None result
            self.stop_running_hooks = True
        item.ihook.pytest_runtest_logstart(nodeid=item.nodeid, location=item.location)

    @override
    def end_test(
        self,
        data: running.TestCase,
        result: result.TestCase,  # pylint:disable=redefined-outer-name
    ):
        item = self._get_item(data)

        # call end test hooks and finish hookwrappers:
        item.ihook.pytest_runtest_logfinish(nodeid=item.nodeid, location=item.location)
        if self.stop_running_hooks:
            self.stop_running_hooks = False  # for next time
        else:
            _ = self._call_hooks(item, self.end_test_hooks)

        # remove all the hooks since they need to be re-evaluated for each item, since items can
        # have different hooks depending on what conftest files are nearby:
        self.start_test_hooks.clear()
        self.end_test_hooks.clear()
        self.hookwrappers.clear()


@catch_errors
class ErrorDetector(ListenerV3):
    """since errors logged by robot don't raise an exception and therefore won't cause the pytest
    test to fail (or even the robot test unless `--exitonerror` is enabled), we need to listen for
    errors and save them to the item to be used in the plugin's `pytest_runtest_makereport` hook
    """

    def __init__(self, *, session: Session, item: Item | None = None) -> None:
        super().__init__()
        self.session = session
        self.item = item
        self.current_test: running.TestCase | None = None

    @override
    def start_test(
        self,
        data: running.TestCase,
        result: result.TestCase,  # pylint:disable=redefined-outer-name
    ):
        if not self.item:
            self.current_test = data

    @override
    def end_test(
        self,
        data: running.TestCase,
        result: result.TestCase,  # pylint:disable=redefined-outer-name
    ):
        if not self.item:
            self.current_test = None

    @override
    def log_message(self, message: model.Message):
        if message.level != "ERROR":
            return
        if self.item:
            item_or_session = self.item
        elif not self.current_test:
            raise InternalError(
                "a robot error occurred and ErrorDetector failed to figure out what test it came"
                + f"from: {message.message}"
            )
        else:
            item_or_session = (
                get_item_from_robot_test(self.session, self.current_test) or self.session
            )
        add_robot_error(item_or_session, message.message)


@catch_errors
class AnsiLogger(ListenerV3):
    esc = "\N{ESCAPE}"

    def __init__(self):
        super().__init__()
        self.current_test_status_contains_ansi = False

    @override
    def start_test(self, data: running.TestCase, result: result.TestCase):  # pylint:disable=redefined-outer-name
        self.current_test_status_contains_ansi = False

    @override
    def log_message(self, message: Message):
        if self.esc in message.message and not message.html:
            self.current_test_status_contains_ansi = True
            message.html = True
            message.message = Ansi2HTMLConverter(inline=True).convert(message.message, full=False)

    @override
    def end_test(self, data: running.TestCase, result: result.TestCase):  # pylint:disable=redefined-outer-name
        if self.current_test_status_contains_ansi:
            self.current_test_status_contains_ansi = False
            result.message = sub(rf"{self.esc}\[.*?m", "", result.message)
