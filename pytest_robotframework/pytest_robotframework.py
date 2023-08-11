from pathlib import Path
from types import ModuleType
from typing import Literal, cast

from _pytest._code.code import ExceptionInfo, ExceptionRepr
from _pytest.runner import call_and_report, show_test_item
from basedtyping import Function
from pytest import (
    Function as PytestFunction,
    Item,
    Parser as PytestParser,
    Session,
    StashKey,
    TestReport,
)
from robot.api import TestSuite as RunningTestSuite
from robot.api.interfaces import Parser as RobotParser, TestDefaults
from robot.libraries.BuiltIn import BuiltIn
from robot.run import RobotFramework
from robot.running.model import Body, Keyword, TestCase as RunningTestCase
from typing_extensions import override


class PytestRobotParser(RobotParser):
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

        def create_keyword_handler(module: ModuleType, fn: Function) -> str:
            """when robot parses a test suite, there's no way to specify function references for the keywords, only the name.
            then when the test is executed, the execution context creates a handler which imports the modules used by the
            suite, which is where it resolves the keywords by name.

            so since we are defining arbitrary functions here that robot needs to be able to find in a module, we have to
            dynamically add it to the specified module with a unique name"""
            suite.resource.imports.library(module.__name__)
            unique_name = fn.__name__
            i = 0
            while hasattr(module, unique_name):
                unique_name = f"{unique_name}_{i}"
                i = i + 1
            setattr(module, unique_name, fn)
            return unique_name

        def call_and_report_robot_edition(
            item: Item, when: Literal["setup", "call", "teardown"], **kwargs: object
        ):
            """wrapper for the `call_and_report` function used by `_pytest.runner.runtestprotocol`
            with additional logic to show the result in the robot log"""
            if report_key in item.stash:
                reports = item.stash[report_key]
            else:
                reports = list[TestReport]()
                item.stash[report_key] = reports
            report = call_and_report(  # type:ignore[no-untyped-call]
                item, when, log=True, **kwargs
            )
            reports.append(report)
            if report.skipped:
                BuiltIn().skip("")  # type:ignore[no-untyped-call]
            elif report.failed:
                # make robot show the exception:
                # TODO: whats up with longrepr why is it such a pain in the ass to use?
                #  is there an easier way to just get the exception/error message?
                longrepr = report.longrepr
                if isinstance(longrepr, ExceptionInfo):
                    raise longrepr.value
                error_text = f"please report this on the pytest-robotframework github repo: {longrepr}"
                if isinstance(longrepr, ExceptionRepr):
                    raise Exception(
                        longrepr.reprcrash.message
                        if longrepr.reprcrash
                        else f"pytest exception was `None`, {error_text}"
                    )
                raise Exception(f"Unknown exception type appeared, {error_text}")

        for item in self.session.items:
            if (
                # TODO: what items are not Functions?
                not isinstance(item, PytestFunction)
                # only add tests from the pytest session that are in the suite robot is parsing
                or item.path != source
            ):
                continue
            function = cast(Function, item.function)
            test_case = RunningTestCase(
                name=item.originalname,
                doc=function.__doc__ or "",
                tags=[marker.name for marker in item.iter_markers()],
            )
            module = cast(ModuleType, item.module)
            if module.__doc__ and not suite.doc:
                suite.doc = module.__doc__
            test_case.body = Body()

            def setup(item: Item = item):
                # mostly copied from the start of `_pytest.runner.runtestprotocol`
                if hasattr(item, "_request") and not item._request:  # type: ignore[no-any-expr]
                    # This only happens if the item is re-run, as is done by
                    # pytest-rerunfailures.
                    item._initrequest()  # type: ignore[attr-defined]
                call_and_report_robot_edition(item, "setup")

            test_case.setup = Keyword(  # type:ignore[assignment]
                name=create_keyword_handler(module, setup), type=Keyword.SETUP
            )

            def run_test(item: Item = item):
                # mostly copied from the middle of `_pytest.runner.runtestprotocol`
                # TODO: this function never gets run if the test is skipped, which deviates from runtestprotocol's behavior
                reports = item.stash[report_key]
                if reports[0].passed:
                    if item.config.getoption(  # type:ignore[no-any-expr,no-untyped-call]
                        "setupshow", False
                    ):
                        show_test_item(item)
                    if not item.config.getoption(  # type:ignore[no-any-expr,no-untyped-call]
                        "setuponly", False
                    ):
                        call_and_report_robot_edition(item, "call")

            # TODO: make this not use a keyword https://github.com/DetachHead/pytest-robotframework/issues/2
            test_case.body.append(
                Keyword(name=create_keyword_handler(module, run_test))
            )

            def teardown(item: Item = item):
                # mostly copied from the end of `_pytest.runner.runtestprotocol`
                call_and_report_robot_edition(
                    item, "teardown", nextitem=item.nextitem  # type:ignore[no-any-expr]
                )

            test_case.teardown = Keyword(
                name=create_keyword_handler(module, teardown), type=Keyword.TEARDOWN
            )
            suite.tests.append(test_case)
        return suite

    @override
    def parse_init(self, source: Path, defaults: TestDefaults) -> RunningTestSuite:
        return RunningTestSuite()


report_key = StashKey[list[TestReport]]()

# these functions are called by pytest and require the arguments with these names even if they are not used
# ruff: noqa: ARG001


def pytest_addoption(parser: PytestParser):
    parser.addoption(
        "--robotargs",
        default="",
        help="additional arguments to be passed to robotframework",
    )


def pytest_runtestloop(session: Session) -> object:
    if session.config.option.collectonly:  # type:ignore[no-any-expr]
        return None
    robot = RobotFramework()  # type:ignore[no-untyped-call]
    robot.main(  # type:ignore[no-untyped-call]
        [session.path],  # type:ignore[no-any-expr]
        parser=[PytestRobotParser(session=session)],  # type:ignore[no-any-expr]
        extension="py",
        **robot.parse_arguments(  # type:ignore[no-any-expr]
            [
                *cast(
                    str,
                    session.config.getoption(  # type:ignore[no-any-expr,no-untyped-call]
                        "--robotargs"
                    ),
                ).split(" "),
                session.path,  # not actually used here, but the argument parser requires at least one path
            ]
        )[0],
    )
    return True
