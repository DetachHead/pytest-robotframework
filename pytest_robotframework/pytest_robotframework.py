from pathlib import Path
from types import ModuleType
from typing import cast

from pytest import Function, Session
from robot.model.testcase import TestCases
from robot.running.model import Body, Keyword, TestCase, TestSuite

suite: TestSuite


def pytest_sessionstart(session: Session):
    global suite
    suite = TestSuite(name=session.name, source=Path(__file__))
    suite.tests = TestCases(tests=[])  # type:ignore[no-any-expr]


def pytest_pyfunc_call(pyfuncitem: Function):
    suite.resource.imports.library(cast(ModuleType, pyfuncitem.module).__name__)
    test_case = TestCase(name=pyfuncitem.name)
    test_case.body = Body(
        items=[Keyword(name=pyfuncitem.name)]  # type:ignore[no-any-expr]
    )
    suite.tests.append(test_case)


def pytest_sessionfinish(session: Session, exitstatus: int):  # noqa: ARG001
    suite.run()  # type:ignore[no-untyped-call]
