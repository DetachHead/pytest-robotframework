from __future__ import annotations

from typing import TYPE_CHECKING, cast

from deepmerge import always_merger
from robot.api import SuiteVisitor
from robot.libraries.BuiltIn import BuiltIn
from robot.run import RobotFramework
from typing_extensions import override

from pytest_robotframework import _suite_variables
from pytest_robotframework._common import (
    KeywordNameFixer,
    PytestRuntestLogListener,
    PytestRuntestProtocolInjector,
    RobotArgs,
    parse_robot_args,
)
from pytest_robotframework._python import PythonParser
from pytest_robotframework._robot import (
    CollectedTestsFilterer,
    RobotFile,
    RobotItem,
    collected_robot_suite_key,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import Collector, Item, Parser, Session
    from robot import model


def pytest_addoption(parser: Parser):
    parser.addoption(
        "--robotargs",
        default="",
        help="additional arguments to be passed to robotframework",
    )


def pytest_collection(session: Session):
    collected_suite: model.TestSuite | None = None

    class RobotTestCollector(SuiteVisitor):
        @override
        def visit_suite(self, suite: model.TestSuite):
            nonlocal collected_suite
            # copy the suite since we want to remove everything from it to prevent robot from running anything
            # but still want to preserve them in `collected_suite`
            collected_suite = suite.deepcopy()  # type:ignore[no-untyped-call]
            suite.suites.clear()  # type:ignore[no-untyped-call]
            suite.tests.clear()  # type:ignore[no-untyped-call]

    robot = RobotFramework()  # type:ignore[no-untyped-call]
    robot.main(  # type:ignore[no-untyped-call]
        [session.path],  # type:ignore[no-any-expr]
        extension="robot",
        runemptysuite=True,
        console="none",
        report=None,
        output=None,
        log=None,
        prerunmodifier=[
            CollectedTestsFilterer(session),
            RobotTestCollector(),
        ],  # type:ignore[no-any-expr]
    )
    if not collected_suite:
        raise Exception("failed to collect .robot tests")
    session.stash[collected_robot_suite_key] = collected_suite


def pytest_collect_file(parent: Collector, file_path: Path) -> Collector | None:
    if file_path.suffix == ".robot":
        return RobotFile.from_parent(  # type:ignore[no-untyped-call,no-any-expr,no-any-return]
            parent, path=file_path
        )
    return None


def pytest_runtest_setup(item: Item):
    if isinstance(item, RobotItem):
        # setting suite variables with the `set_variables` function is only supported in python files.
        # when running robot files, suite variables should be set using the `*** Variables ***` section
        return
    builtin = BuiltIn()
    for key, value in _suite_variables[item.path].items():
        builtin.set_suite_variable(r"${" + key + "}", value)


def pytest_runtestloop(session: Session) -> object:
    if session.config.option.collectonly:  # type:ignore[no-any-expr]
        return None
    robot = RobotFramework()  # type:ignore[no-untyped-call]
    robot.main(  # type:ignore[no-untyped-call]
        [session.path],  # type:ignore[no-any-expr]
        extension="py:robot",
        **cast(
            RobotArgs,
            always_merger.merge(  # type:ignore[no-untyped-call]
                parse_robot_args(robot, session),
                dict[str, object](
                    parser=[PythonParser(session)],
                    prerunmodifier=[
                        CollectedTestsFilterer(session),
                        PytestRuntestProtocolInjector(session),
                    ],
                    prerebotmodifier=[KeywordNameFixer()],
                    listener=[PytestRuntestLogListener(session)],
                ),
            ),
        ),
    )
    return True
