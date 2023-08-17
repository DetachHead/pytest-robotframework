from __future__ import annotations

from pathlib import Path
from typing import cast

from deepmerge import always_merger
from pytest import Collector, Item, Parser, Session
from robot import model
from robot.api import SuiteVisitor
from robot.libraries.BuiltIn import BuiltIn
from robot.run import RobotFramework

from pytest_robotframework import _suite_variables
from pytest_robotframework._common import (
    KeywordNameFixer,
    PytestRuntestLogListener,
    PytestRuntestProtocolInjector,
    RobotArgs,
    parse_robot_args,
)
from pytest_robotframework._python import PythonParser
from pytest_robotframework._robot import RobotFile, RobotItem, collected_robot_suite_key


def pytest_addoption(parser: Parser):
    parser.addoption(
        "--robotargs",
        default="",
        help="additional arguments to be passed to robotframework",
    )


def pytest_collectstart(collector: Collector):
    collected_suite: model.TestSuite | None = None

    class RobotTestCollector(SuiteVisitor):
        def end_suite(self, suite: model.TestSuite):
            nonlocal collected_suite
            collected_suite = suite

    robot = RobotFramework()  # type:ignore[no-untyped-call]
    robot.main(  # type:ignore[no-untyped-call]
        [collector.session.path],  # type:ignore[no-any-expr]
        extension="robot",
        dryrun=True,
        runemptysuite=True,
        console="none",
        prerunmodifier=[RobotTestCollector()],  # type:ignore[no-any-expr]
    )
    if not collected_suite:
        raise Exception("failed to collect .robot tests")
    collector.session.stash[collected_robot_suite_key] = collected_suite


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
                    prerunmodifier=[PytestRuntestProtocolInjector(session)],
                    prerebotmodifier=[KeywordNameFixer()],
                    listener=[PytestRuntestLogListener(session)],
                ),
            ),
        ),
    )
    return True
