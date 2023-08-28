import re
from types import ModuleType

# callable isnt a collection
from typing import Callable, Literal, cast  # noqa: UP035

from _pytest._code.code import (  # pylint:disable=import-private-name
    ExceptionInfo,
    ExceptionRepr,
)
from _pytest.runner import (  # pylint:disable=import-private-name
    call_and_report,
    show_test_item,
)
from pytest import Function, Item, Session, StashKey, TestReport
from robot import model, result, running
from robot.api import ResultVisitor, SuiteVisitor
from robot.api.deco import keyword
from robot.api.interfaces import ListenerV3
from robot.libraries.BuiltIn import BuiltIn
from robot.running.model import Body
from typing_extensions import override

from pytest_robotframework import _fake_robot_library

KeywordFunction = Callable[[], None]


collected_robot_suite_key = StashKey[model.TestSuite]()
running_test_case_key = StashKey[running.TestCase]()


class PytestRobotFrameworkError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(
            "something went wrong with the pytest-robotframework plugin. please raise"
            " an issue at https://github.com/detachhead/pytest-robotframework with the"
            f" following information:\n\n{message}"
        )


def get_item_from_robot_test(session: Session, test: running.TestCase) -> Item | None:
    try:
        return next(
            item for item in session.items if item.stash[running_test_case_key] == test
        )
    except StopIteration:
        # the robot test was found but got filtered out by pytest
        return None


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

    @override
    def visit_suite(self, suite: running.TestSuite):
        if not suite.parent:  # only do this once, on the top level suite
            self.session.stash[collected_robot_suite_key] = suite
            self.session.perform_collect()
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
            suite.suites.clear()  # type:ignore[no-untyped-call]
            suite.tests.clear()  # type:ignore[no-untyped-call]
            return
        if suite.source and suite.source.suffix != ".robot":
            # remove the fake test (required so that the parser doesn't delete suites for being
            # empty)
            suite.tests.clear()  # type:ignore[no-untyped-call]

        # remove any .robot tests that were filtered out by pytest:
        for test in suite.tests[:]:
            if not get_item_from_robot_test(self.session, test):
                # happens when running .robot tests that were filtered out by pytest
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


class KeywordNameFixer(ResultVisitor):
    """renames our dynamically generated setup/call/teardown keywords in the log back to user
    friendly ones"""

    @override
    # supertype is wrong, TODO: raise robot issue
    def visit_keyword(
        self,
        keyword: result.Keyword,  # type:ignore[override] #pylint:disable=redefined-outer-name
    ):
        keyword.kwname = re.sub(
            r"pytestrobotkeyword\d+ ", "", keyword.kwname, flags=re.IGNORECASE
        )


original_setup_key = StashKey[model.Keyword]()
original_body_key = StashKey[Body]()
original_teardown_key = StashKey[model.Keyword]()


def register_keyword(suite: running.TestSuite, fn: KeywordFunction) -> str:
    """when robot parses a test suite, there's no way to specify function references for the
    keywords, only the name. then when the test is executed, the execution context creates a handler
    which imports the modules used by the suite, which is where it resolves the keywords by name.

    so since we are defining arbitrary functions here that robot needs to be able to find in a
    module, we have to dynamically add it to our fake module with a unique name.

    after the test suite is run, `KeywordNameFixer` modifies the run results to change the keyword
    names back to non-unique user friendly ones"""
    suite.resource.imports.library(_fake_robot_library.__name__)
    name = f"pytestrobotkeyword{hash(fn)}_{fn.__name__}"
    setattr(_fake_robot_library, name, keyword(fn))  # type:ignore[no-any-expr]
    return name


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
        self.report_key = StashKey[list[TestReport]]()

    def _call_and_report_robot_edition(
        self, item: Item, when: Literal["setup", "call", "teardown"], **kwargs: object
    ):
        """wrapper for the `call_and_report` function used by `_pytest.runner.runtestprotocol`
        with additional logic to show the result in the robot log"""
        if self.report_key in item.stash:
            reports = item.stash[self.report_key]
        else:
            reports = list[TestReport]()
            item.stash[self.report_key] = reports
        report = call_and_report(  # type:ignore[no-untyped-call]
            item, when, log=True, **kwargs
        )
        reports.append(report)
        if report.skipped:
            # empty string means xfail with no reason, None means it was not an xfail
            xfail_reason = (
                cast(str, report.wasxfail) if hasattr(report, "wasxfail") else None
            )
            BuiltIn().skip(  # type:ignore[no-untyped-call]
                # TODO: is there a reliable way to get the reason when skipped by a skip/skipif marker?
                # https://github.com/DetachHead/pytest-robotframework/issues/51
                ""
                if xfail_reason is None
                else ("xfail" + (f": {xfail_reason}" if xfail_reason else ""))
            )
        elif report.failed:
            # make robot show the exception:
            # TODO: whats up with longrepr why is it such a pain in the ass to use?
            #  is there an easier way to just get the exception/error message?
            #  https://github.com/DetachHead/pytest-robotframework/issues/35
            longrepr = report.longrepr
            if isinstance(longrepr, str):
                # xfail strict
                raise Exception(longrepr)
            if isinstance(longrepr, ExceptionRepr):
                if longrepr.reprcrash:
                    # normal failures
                    raise Exception(longrepr.reprcrash.message)
                raise PytestRobotFrameworkError(
                    f"pytest exception reprcrash was `None`: {longrepr}"
                )
            if isinstance(longrepr, ExceptionInfo):
                raise PytestRobotFrameworkError(
                    f"got unexpected exception type: {longrepr.value}"
                )
            raise PytestRobotFrameworkError(
                f"Unknown exception type appeared: {longrepr}"
            )

    @override
    def start_suite(self, suite: running.TestSuite):
        for test in suite.tests:
            item = get_item_from_robot_test(self.session, test)
            if not item:
                raise PytestRobotFrameworkError(
                    "this should NEVER happen, `PytestCollector` failed to filter out"
                    f" {test.name}"
                )

            # https://github.com/python/mypy/issues/15894
            def setup(item: Item = item):  # type:ignore[assignment]
                # mostly copied from the start of `_pytest.runner.runtestprotocol`
                if (
                    hasattr(item, "_request")
                    and not item._request  # type: ignore[no-any-expr] # noqa: SLF001
                ):
                    # This only happens if the item is re-run, as is done by
                    # pytest-rerunfailures.
                    item._initrequest()  # type: ignore[attr-defined] # noqa: SLF001
                self._call_and_report_robot_edition(item, "setup")

            item.stash[original_setup_key] = test.setup
            test.setup = running.Keyword(  # type:ignore[assignment]
                name=register_keyword(suite, setup), type=model.Keyword.SETUP
            )

            def run_test(item: Item = item):  # type:ignore[assignment]
                # mostly copied from the middle of `_pytest.runner.runtestprotocol`
                reports = item.stash[self.report_key]
                if reports[0].passed:
                    if item.config.getoption(  # type:ignore[no-any-expr,no-untyped-call]
                        "setupshow", default=False
                    ):
                        show_test_item(item)
                    if not item.config.getoption(  # type:ignore[no-any-expr,no-untyped-call]
                        "setuponly", default=False
                    ):
                        self._call_and_report_robot_edition(item, "call")

            # TODO: what is this mypy error
            #  https://github.com/DetachHead/pytest-robotframework/issues/36
            item.stash[original_body_key] = test.body  # type:ignore[misc]
            test.body = Body(
                items=[running.Keyword(name=register_keyword(suite, run_test))]
            )

            def teardown(item: Item = item):  # type:ignore[assignment]
                # mostly copied from the end of `_pytest.runner.runtestprotocol`
                self._call_and_report_robot_edition(
                    item, "teardown", nextitem=item.nextitem  # type:ignore[no-any-expr]
                )

            item.stash[original_teardown_key] = test.teardown
            test.teardown = running.Keyword(
                name=register_keyword(suite, teardown), type=model.Keyword.TEARDOWN
            )


class PytestRuntestLogListener(ListenerV3):
    """runs the `pytest_runtest_logstart` and `pytest_runtest_logfinish` hooks from
    `pytest_runtest_protocol`. since all the other parts of `_pytest.runner.runtestprotocol` are
    re-implemented in `PytestRuntestProtocolInjector`
    """

    def __init__(self, session: Session):
        self.session = session

    def _get_item(self, data: running.TestCase) -> Item:
        item = get_item_from_robot_test(self.session, data)
        if not item:
            raise PytestRobotFrameworkError(
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
