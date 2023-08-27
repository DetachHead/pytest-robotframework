from __future__ import annotations

from typing import TYPE_CHECKING

from robot import running
from robot.api.interfaces import Parser, TestDefaults
from typing_extensions import override

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import Session


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
        result = self._create_suite(source)
        # this fake test is required to prevent the suite from being deleted before the
        # prerunmodifiers are called
        test_case = running.TestCase(name="fake test you shoud NEVER see this!!!!!!!")
        test_case.body = [running.Keyword("fail")]
        result.tests.append(test_case)
        return result

    @override
    def parse_init(self, source: Path, defaults: TestDefaults) -> running.TestSuite:
        return self._create_suite(source)
