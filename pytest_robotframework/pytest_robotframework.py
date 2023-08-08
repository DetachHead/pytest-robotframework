from pathlib import Path
from types import ModuleType
from typing import Literal, cast

from pytest import CallInfo, Function, Item, Session, StashKey, TestReport
from robot.model.testcase import TestCases
from robot.result.executionresult import Result
from robot.result.model import TestCase as ResultTestCase
from robot.running.model import Body, Keyword, TestCase as ModelTestCase, TestSuite

test_result = StashKey[Result]()

# these functions are called by pytest and require the arguments with these names even if they are not used
# ruff: noqa: ARG001


def pytest_runtestloop(session: Session):
    suite = TestSuite(name=session.name, source=Path(__file__))
    suite.tests = TestCases(tests=[])  # type:ignore[no-any-expr]
    for test in session.items:
        if not isinstance(test, Function):
            continue
        suite.resource.imports.library(cast(ModuleType, test.module).__name__)
        test_case = ModelTestCase(name=test.originalname)
        test_case.body = Body(
            items=[Keyword(name=test.originalname)]  # type:ignore[no-any-expr]
        )
        suite.tests.append(test_case)  # type:ignore[no-any-expr]

    session.stash[
        test_result
    ] = suite.run()  # type:ignore[no-untyped-call,func-returns-value]


def pytest_pyfunc_call(pyfuncitem: Function) -> object:
    """prevent pytest from running the function because robot runs it later"""
    return True


def pytest_runtest_makereport(item: Item, call: CallInfo[None]) -> TestReport | None:
    if call.when != "call" or not isinstance(item, Function):
        return None
    robot_suite_result = item.session.stash[test_result]
    robot_test_result: ResultTestCase = next(
        robot_test
        for robot_test in cast(
            TestCases[ResultTestCase], cast(TestSuite, robot_suite_result.suite).tests
        )
        if robot_test.name == item.originalname  # type:ignore[no-any-expr]
    )
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
