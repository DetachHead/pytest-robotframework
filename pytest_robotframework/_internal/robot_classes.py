"""robot parsers, prerunmodifiers and listeners that the plugin (`pytest_robotframework.py`) uses
when running robot (some of them are not activated when running pytest in `--collect-only` mode)"""

from __future__ import annotations

from types import ModuleType

# callable is not a collection
from typing import TYPE_CHECKING, Callable, Literal, ParamSpec, cast  # noqa: UP035

from pytest import Function, Item, Session, StashKey, UsageError
from robot import model, result, running
from robot.api import SuiteVisitor
from robot.api.interfaces import ListenerV3, Parser, TestDefaults
from robot.running.model import Body
from typing_extensions import override

from pytest_robotframework._internal import robot_library
from pytest_robotframework._internal.errors import InternalError
from pytest_robotframework._internal.robot_library import internal_error

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
        raise internal_error(
            f"kwargs not supported: {kwargs}"
        )  # type:ignore[no-any-expr]
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
                "fake placeholder test appeared. this should never happen :((",
            )
        ]
        suite.tests.append(test_case)
        return suite

    @override
    def parse_init(self, source: Path, defaults: TestDefaults) -> running.TestSuite:
        return self._create_suite(source.parent)


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
        self.collection_error: UsageError | None = None

    @override
    def visit_suite(self, suite: running.TestSuite):
        if not suite.parent:  # only do this once, on the top level suite
            self.session.stash[collected_robot_suite_key] = suite
            try:
                self.session.perform_collect()
            except UsageError as e:
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


class PytestRuntestProtocolInjector(SuiteVisitor):
    """injects the hooks from `pytest_runtest_protocol` into the robot test suite. this replaces any
     existing setup/body/teardown with said hooks, which may or may not be an issue depending on
     whether a python or robot test is being run.

    - if running a `.robot` test: the test cases would already have setup/body/teardown keywords, so
    make sure the hooks actually call those keywords (`original_setup_key`, `original_body_key` and
    `original_teardown_key` stashes are used to send the original keywords to the methods on
    `RobotFile`)
    - if running a `.py` test, this is not an issue because the robot test cases are empty (see
    `PythonParser`) and the hook functions already have the actual contents of the tests, because
    they are just plain pytest tests
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

            item.stash[original_setup_key] = test.setup
            # TODO: whats this mypy error
            #  https://github.com/DetachHead/pytest-robotframework/issues/36
            test.setup = _create_running_keyword(  # type:ignore[assignment]
                "SETUP",
                robot_library.setup,  # type:ignore[no-any-expr]
                item,
            )

            item.stash[original_body_key] = test.body  # type:ignore[misc]
            test.body = Body(
                items=[
                    _create_running_keyword(
                        "KEYWORD",
                        robot_library.run_test,  # type:ignore[no-any-expr]
                        item,
                    )
                ]
            )

            item.stash[original_teardown_key] = test.teardown
            test.teardown = _create_running_keyword(
                "TEARDOWN",
                robot_library.teardown,  # type:ignore[no-any-expr]
                item,
            )


class PytestRuntestLogListener(ListenerV3):
    """runs the `pytest_runtest_logstart` and `pytest_runtest_logfinish` hooks from
    `pytest_runtest_protocol`. since all the other parts of `_pytest.runner.runtestprotocol` are
    re-implemented in `PytestRuntestProtocolInjector`
    """

    def __init__(self, session: Session):
        self.session = session

    def _get_item(self, data: running.TestCase) -> Item:
        item = _get_item_from_robot_test(self.session, data)
        if not item:
            raise InternalError(
                f"failed to find pytest item for robot test: {data.name}"
            )
        return item

    @override
    def start_test(
        self,
        data: running.TestCase,
        result: result.TestCase,  # pylint:disable=redefined-outer-name
    ):
        item = self._get_item(data)
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
