from pathlib import Path
from types import ModuleType
from typing import Literal, cast

from pytest import CallInfo, Function, Item, Session, StashKey, TestReport
from robot.api import TestSuite as RunningTestSuite
from robot.api.interfaces import ListenerV3, Parser, TestDefaults
from robot.result.model import TestCase as ResultTestCase, TestSuite as ResultTestSuite
from robot.run import RobotFramework
from robot.running.model import Body, Keyword, TestCase as RunningTestCase
from typing_extensions import override


class PytestParser(Parser):
    """custom robot "parser" for pytest files. doesn't actually do any parsing,
    but instead creates the test suites using the pytest session. this requires
    the tests to have already been collected by pytest"""

    def __init__(self, session: Session) -> None:
        self.session = session
        super().__init__()

    extension = "py"

    @override
    def parse(self, source: Path, defaults: TestDefaults) -> RunningTestSuite:
        suite = RunningTestSuite(
            RunningTestSuite.name_from_source(source), source=source
        )
        for test in self.session.items:
            if (
                # TODO: what items are not Functions?
                not isinstance(test, Function)
                # only add tests from the pytest session that are in the suite robot is parsing
                or test.path != source
            ):
                continue
            test_case = RunningTestCase(name=test.originalname)
            test_case.body = Body()
            for marker in test.iter_markers():
                if marker.name == "skip":
                    keyword = Keyword("skip")
                elif marker.name == "skipif":
                    # TODO: styring conditions? but i think they're deprecated and/or cringe so who cares
                    condition: object = (
                        marker.args[0]  # type:ignore[no-any-expr]
                        or marker.kwargs["condition"]  # type:ignore[no-any-expr]
                    )
                    keyword = Keyword(
                        "skip if",
                        (
                            str(condition),
                            marker.kwargs["reason"],  # type:ignore[no-any-expr]
                        ),
                    )
                else:
                    continue
                test_case.body.append(keyword)
            # TODO: make this not use a keyword https://github.com/DetachHead/pytest-robotframework/issues/2
            test_case.body.append(Keyword(name=test.originalname))
            suite.resource.imports.library(cast(ModuleType, test.module).__name__)
            suite.tests.append(test_case)
        return suite

    @override
    def parse_init(self, source: Path, defaults: TestDefaults) -> RunningTestSuite:
        return RunningTestSuite()


class RobotResultGetter(ListenerV3):
    """listener to get the test results from the robot run"""

    def __init__(self) -> None:
        self.results = list[ResultTestSuite]()
        super().__init__()

    @override
    def end_suite(self, data: RunningTestSuite, result: ResultTestSuite):
        self.results.append(result)


result_getter_key = StashKey[RobotResultGetter]()

# these functions are called by pytest and require the arguments with these names even if they are not used
# ruff: noqa: ARG001


def pytest_pyfunc_call(pyfuncitem: Function) -> object:
    """prevent pytest from running the function because robot runs it instead in `pytest_runtestloop`"""
    return True


def pytest_runtestloop(session: Session):
    result_getter = RobotResultGetter()
    session.stash[result_getter_key] = result_getter
    RobotFramework().main(  # type:ignore[no-untyped-call]
        [session.path],  # type:ignore[no-any-expr]
        parser=[PytestParser(session=session)],  # type:ignore[no-any-expr]
        listener=[result_getter],  # type:ignore[no-any-expr]
        extension="py",
    )


def pytest_runtest_makereport(item: Item, call: CallInfo[None]) -> TestReport | None:
    if call.when != "call" or not isinstance(item, Function):
        return None
    robot_test_result: ResultTestCase | None = None
    for suite in item.session.stash[result_getter_key].results:
        for test in suite.tests:
            if (
                test.name == item.originalname
                and str(test.source) == item.module.__file__  # type:ignore[no-any-expr]
            ):
                robot_test_result = test
                break
        if robot_test_result:
            break
    else:
        raise Exception(f"failed to find robot test for {item.originalname}")
    outcomes: dict[str, Literal["passed", "failed", "skipped"]] = {
        robot_test_result.FAIL: "failed",
        robot_test_result.PASS: "passed",
        robot_test_result.SKIP: "skipped",
    }
    return TestReport(
        nodeid=item.nodeid,
        location=item.location,
        keywords=item.keywords,  # type:ignore[no-any-expr]
        outcome=outcomes[robot_test_result.status],
        longrepr=robot_test_result.message,
        when=call.when,
    )
