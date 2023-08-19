from __future__ import annotations

from types import ModuleType
from typing import TYPE_CHECKING, cast

from basedtyping import Function
from pytest import Function as PytestFunction, Session
from robot import running
from robot.api.interfaces import Parser as RobotParser, TestDefaults
from robot.running.model import Body
from typing_extensions import override

from pytest_robotframework._common import running_test_case_key

if TYPE_CHECKING:
    from pathlib import Path


class PythonParser(RobotParser):
    """custom robot "parser" for python files. doesn't actually do any parsing,
    but instead creates the test suites using the pytest session. this requires
    the tests to have already been collected by pytest

    the tests created by the parser are empty, until the `PytestRuntestProtocolInjector`
    prerunmodifier injects the pytest hook functions into them, which are responsible
    for actually running the setup/call/teardown functions"""

    def __init__(self, session: Session) -> None:
        self.session = session
        super().__init__()

    extension = "py"

    @override
    def parse(self, source: Path, defaults: TestDefaults) -> running.TestSuite:
        suite = running.TestSuite(
            running.TestSuite.name_from_source(source), source=source
        )
        for item in self.session.items:
            if (
                # don't include RobotItems as .robot files are parsed by robot's default parser
                not isinstance(item, PytestFunction)
                # only add tests from the pytest session that are in the suite robot is parsing
                or item.path != source
            ):
                continue
            test_case = running.TestCase(
                name=item.name,
                doc=cast(Function, item.function).__doc__ or "",
                tags=[marker.name for marker in item.iter_markers()],
            )
            item.stash[running_test_case_key] = test_case
            module = cast(ModuleType, item.module)
            if module.__doc__ and not suite.doc:
                suite.doc = module.__doc__
            test_case.body = Body()
            suite.tests.append(test_case)
        return suite

    @override
    def parse_init(self, source: Path, defaults: TestDefaults) -> running.TestSuite:
        return running.TestSuite()
