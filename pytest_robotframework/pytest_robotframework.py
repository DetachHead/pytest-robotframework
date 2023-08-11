from pathlib import Path
from types import ModuleType
from typing import Literal, cast

from _pytest.config.compat import PathAwareHookProxy
from _pytest.outcomes import Skipped
from _pytest.runner import (
    call_runtest_hook,
    check_interactive_exception,
    show_test_item,
)
from basedtyping import Function
from pytest import (
    CallInfo,
    Function as PytestFunction,
    Item,
    Parser as PytestParser,
    Session,
    StashKey,
    TestReport,
)
from robot.api import TestSuite as RunningTestSuite
from robot.api.interfaces import ListenerV3, Parser as RobotParser, TestDefaults
from robot.libraries.BuiltIn import BuiltIn
from robot.result.model import TestCase as ResultTestCase
from robot.run import RobotFramework
from robot.running.model import Body, Keyword, TestCase as RunningTestCase
from typing_extensions import override

PytestTestStage = Literal["setup", "call", "teardown"]


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

        for item in self.session.items:
            if (
                # TODO: what items are not Functions?
                not isinstance(item, PytestFunction)
                # only add tests from the pytest session that are in the suite robot is parsing
                or item.path != source
            ):
                continue
            test_case = RunningTestCase(name=item.originalname)
            item.stash[running_test_key] = test_case
            module = cast(ModuleType, item.module)
            test_case.body = Body()

            def setup(item: Item = item):
                """mostly copied from the start of `_pytest.runner.runtestprotocol`
                (reporting section moved to `pytest_report`)"""
                if hasattr(item, "_request") and not item._request:  # type: ignore[no-any-expr]
                    # This only happens if the item is re-run, as is done by
                    # pytest-rerunfailures.
                    item._initrequest()  # type: ignore[attr-defined]
                call = call_runtest_hook(item, "setup")  # type:ignore[no-untyped-call]
                item.stash[calls_key] = [call]
                # make robot show the exception:
                if call.excinfo:
                    exception = call.excinfo.value
                    if isinstance(exception, Skipped):
                        BuiltIn().skip(  # type:ignore[no-untyped-call]
                            "test marked with skip or skipif"
                        )
                    else:
                        raise call.excinfo.value

            test_case.setup = Keyword(  # type:ignore[assignment]
                name=create_keyword_handler(module, setup), type=Keyword.SETUP
            )

            def run_test(item: Item = item):
                """mostly copied from the middle of `_pytest.runner.runtestprotocol`
                (reporting section moved to `pytest_report`)"""
                # the original implementation in runtestprotocol gets the result from the report
                # in the pytest_runtest_makereport hook, but we can't call these yet because robot doesn't
                # give us the status until after setup, call and teardown are finished
                # TODO: this part never gets run if the test is skipped, which deviates from runtestprotocol's behavior
                if not item.stash[calls_key][0].excinfo:
                    if item.config.getoption(  # type:ignore[no-any-expr,no-untyped-call]
                        "setupshow", False
                    ):
                        show_test_item(item)
                    call = call_runtest_hook(
                        item, "call"
                    )  # type:ignore[no-untyped-call]
                    item.stash[calls_key].append(call)
                    # make robot show the exception:
                    if call.excinfo:
                        raise call.excinfo.value

            # TODO: make this not use a keyword https://github.com/DetachHead/pytest-robotframework/issues/2
            test_case.body.append(  # type:ignore[no-any-expr]
                Keyword(name=create_keyword_handler(module, run_test))
            )

            def teardown(item: Item = item):
                """mostly copied from the end of `_pytest.runner.runtestprotocol`
                (reporting section moved to `pytest_report`, _request cleanup thingy
                moved to the `end_test` method of the `ResultReporter` robot listener)
                """
                reports = item.stash[calls_key]
                call = call_runtest_hook(  # type:ignore[no-untyped-call]
                    item, "teardown", nextitem=item.nextitem  # type:ignore[no-any-expr]
                )
                reports.append(call)
                # make robot show the exception:
                if call.excinfo:
                    raise call.excinfo.value

            test_case.teardown = Keyword(
                name=create_keyword_handler(module, teardown), type=Keyword.TEARDOWN
            )
            suite.tests.append(test_case)
        return suite

    @override
    def parse_init(self, source: Path, defaults: TestDefaults) -> RunningTestSuite:
        return RunningTestSuite()


def _pytest_report(item: Item, call: CallInfo[None], log=True) -> TestReport:
    """copied from the last half of `_pytest.runner.call_and_report`"""
    hook = cast(PathAwareHookProxy, item.ihook)
    report: TestReport = hook.pytest_runtest_makereport(item=item, call=call)
    if log:
        hook.pytest_runtest_logreport(report=report)
    if check_interactive_exception(call, report):
        hook.pytest_exception_interact(node=item, call=call, report=report)
    return report


class ResultReporter(ListenerV3):
    """listener to get the test results from the robot run"""

    def __init__(self, session: Session) -> None:
        self.results = list[ResultTestCase]()
        self.session = session
        super().__init__()

    @override
    def end_test(self, data: RunningTestCase, result: ResultTestCase):
        item = next(
            item for item in self.session.items if item.stash[running_test_key] == data
        )
        for when in item.stash[calls_key]:
            _pytest_report(item, when)

        # copied from the end of `_pytest.runner.runtestprotocol`:
        # After all teardown hooks have been called
        # want funcargs and request info to go away.
        if hasattr(item, "_request"):
            item._request = False  # type: ignore[no-untyped-usage]
            item.funcargs = None  # type: ignore[attr-defined]


calls_key = StashKey[list[CallInfo[None]]]()
running_test_key = StashKey[RunningTestCase]()

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
        listener=[ResultReporter(session)],  # type:ignore[no-any-expr]
        extension="py",
        **robot.parse_arguments(  # type:ignore[no-any-expr]
            [
                *cast(
                    str,
                    session.config.getoption(  # type:ignore[no-any-expr,no-untyped-call]
                        "--robotargs"
                    ),
                ).split(" "),
                session.path,  # no
            ]
        )[0],
    )
    return True
