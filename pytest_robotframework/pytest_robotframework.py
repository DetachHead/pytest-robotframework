import re
from pathlib import Path
from types import ModuleType

# Callable is not a collection
from typing import Callable, Literal, cast  # noqa: UP035

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
from robot import result, running
from robot.api import ResultVisitor
from robot.api.deco import keyword
from robot.api.interfaces import Parser as RobotParser, TestDefaults
from robot.libraries.BuiltIn import BuiltIn
from robot.run import RobotFramework
from robot.running.model import Body, Keyword
from typing_extensions import override

from pytest_robotframework import _suite_variables

KeywordFunction = Callable[[], None]


def _register_keyword(
    suite: running.TestSuite, module: ModuleType, fn: KeywordFunction
) -> str:
    """when robot parses a test suite, there's no way to specify function references for the keywords, only the name.
    then when the test is executed, the execution context creates a handler which imports the modules used by the
    suite, which is where it resolves the keywords by name.

    so since we are defining arbitrary functions here that robot needs to be able to find in a module, we have to
    dynamically add it to the specified module with a unique name.

    after the test suite is run, `_KeywordNameFixer` modifies the run results to change the keyword names back to
    non-unique user friendly ones"""
    suite.resource.imports.library(module.__name__)
    name = f"pytestrobotkeyword{hash(fn)}_{fn.__name__}"
    setattr(module, name, keyword(fn))  # type:ignore[no-any-expr]
    return name


class _PytestRobotParser(RobotParser):
    """custom robot "parser" for pytest files. doesn't actually do any parsing,
    but instead creates the test suites using the pytest session. this requires
    the tests to have already been collected by pytest"""

    def __init__(self, session: Session) -> None:
        self.session = session
        super().__init__()

    extension = "py"

    @override
    def parse(self, source: Path, defaults: TestDefaults) -> running.TestSuite:
        report_key = StashKey[list[TestReport]]()
        suite = running.TestSuite(
            running.TestSuite.name_from_source(source), source=source
        )
        builtin = BuiltIn()

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
                builtin.skip("")  # type:ignore[no-untyped-call]
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
            test_case = running.TestCase(
                name=item.name,
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
                for key, value in _suite_variables[source].items():
                    builtin.set_suite_variable(r"${" + key + "}", value)
                call_and_report_robot_edition(item, "setup")

            test_case.setup = Keyword(  # type:ignore[assignment]
                name=_register_keyword(suite, module, setup), type=Keyword.SETUP
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
                Keyword(name=_register_keyword(suite, module, run_test))
            )

            def teardown(item: Item = item):
                # mostly copied from the end of `_pytest.runner.runtestprotocol`
                call_and_report_robot_edition(
                    item, "teardown", nextitem=item.nextitem  # type:ignore[no-any-expr]
                )

            test_case.teardown = Keyword(
                name=_register_keyword(suite, module, teardown), type=Keyword.TEARDOWN
            )
            suite.tests.append(test_case)
        return suite

    @override
    def parse_init(self, source: Path, defaults: TestDefaults) -> running.TestSuite:
        return running.TestSuite()


class _KeywordNameFixer(ResultVisitor):
    """renames our dynamically generated setup/call/teardown keywords in the log back to user friendly ones"""

    @override
    # supertype is wrong, TODO: raise mypy issue
    def visit_keyword(self, keyword: result.Keyword):  # type:ignore[override]
        keyword.kwname = re.sub(
            r"pytestrobotkeyword\d+ ", "", keyword.kwname, flags=re.IGNORECASE
        )


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
        parser=[_PytestRobotParser(session=session)],  # type:ignore[no-any-expr]
        extension="py",
        prerebotmodifier=[_KeywordNameFixer()],  # type:ignore[no-any-expr]
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
