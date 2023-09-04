"""the actual pytest plugin"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest
from deepmerge import always_merger
from pytest import TestReport
from robot.api import logger
from robot.libraries.BuiltIn import BuiltIn
from robot.output import LOGGER
from robot.run import RobotFramework

from pytest_robotframework import (
    _errors,
    _listeners,
    _resources,
    _suite_variables,
    import_resource,
    keyword,
    keywordify,
)
from pytest_robotframework._internal.errors import InternalError
from pytest_robotframework._internal.pytest_robot_items import RobotFile, RobotItem
from pytest_robotframework._internal.robot_classes import (
    ErrorDetector,
    PytestCollector,
    PytestRuntestProtocolHooks,
    PytestRuntestProtocolInjector,
    PythonParser,
    robot_errors_key,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import CallInfo, Collector, Item, Parser, Session


def _collect_slash_run(session: Session, *, collect_only: bool):
    """this is called either by `pytest_collection` or `pytest_runtestloop` depending on whether
    `collect_only` is `True`, because to avoid having to run robot multiple times for both the
    collection and running, it's more efficient to just have `pytest_runtestloop` handle the
    collection as well if possible.
    """
    if _listeners.too_late:
        raise InternalError("somehow ran collect/run twice???")
    robot = RobotFramework()  # type:ignore[no-untyped-call]
    robot_args = cast(
        dict[str, object],
        always_merger.merge(  # type:ignore[no-untyped-call]
            robot.parse_arguments(  # type:ignore[no-any-expr]
                [
                    *cast(
                        str,
                        session.config.getoption(  # type:ignore[no-any-expr,no-untyped-call]
                            "--robotargs"
                        ),
                    ).split(" "),
                    # not actually used here, but the argument parser requires at least one path
                    session.path,
                ]
            )[0],
            dict[str, object](
                parser=[PythonParser(session)],
                prerunmodifier=[PytestCollector(session, collect_only=collect_only)],
            ),
        ),
    )
    if collect_only:
        robot_args |= {"report": None, "output": None, "log": None, "exitonerror": True}
    else:
        robot_args = always_merger.merge(  # type:ignore[no-untyped-call]
            robot_args,
            dict[str, object](
                prerunmodifier=[PytestRuntestProtocolInjector(session)],
                listener=[
                    PytestRuntestProtocolHooks(session),
                    ErrorDetector(session),
                    *_listeners.instances,
                ],
            ),
        )
    _listeners.too_late = True
    # needed for log_file listener methods to prevent logger from deactivating after the test is
    # over
    try:
        with LOGGER:
            robot.main(  # type:ignore[no-untyped-call]
                [session.path],  # type:ignore[no-any-expr]
                extension="py:robot",
                # needed because PythonParser.visit_init creates an empty suite
                runemptysuite=True,
                **robot_args,
            )
    finally:
        _listeners.too_late = False
    if _errors:
        raise ExceptionGroup(
            "the following errors occurred inside robot listeners", _errors
        )


def pytest_addoption(parser: Parser):
    parser.addoption(
        "--robotargs",
        default="",
        help="additional arguments to be passed to robotframework",
    )


def pytest_assertion_pass(orig: str, expl: str):
    """without this hook, passing assertions won't show up at all in the robot log"""

    @keyword(name="assert", module="")
    def assertion(
        # unused argument just for showing it in the robot log
        _expression: str,
    ):
        logger.info(expl)  # type:ignore[no-untyped-call]

    # this matches what's logged if an assertion fails, so we keep it the same here for consistency
    # (idk why there's no pytest_assertion_fail hook, only reprcompare which is different)
    assertion(orig)


def pytest_runtest_makereport(item: Item, call: CallInfo[None]) -> TestReport | None:
    errors = item.stash.get(robot_errors_key, None)
    if errors:
        result = TestReport.from_item_and_call(item, call)
        result.outcome = "failed"
        result.longrepr = (
            f"robot errors detected: {[error.message for error in errors]}"
        )
        del item.stash[robot_errors_key]
        return result
    return None


def pytest_collection(session: Session) -> object:
    if session.config.option.collectonly:  # type:ignore[no-any-expr]
        _collect_slash_run(session, collect_only=True)
    return True


def pytest_collect_file(parent: Collector, file_path: Path) -> Collector | None:
    if file_path.suffix == ".robot":
        return RobotFile.from_parent(  # type:ignore[no-untyped-call,no-any-expr,no-any-return]
            parent, path=file_path
        )
    return None


def pytest_runtest_setup(item: Item):
    if isinstance(item, RobotItem):
        # `set_variables` and `import_resource` is only supported in python files.
        # when running robot files, suite variables should be set using the `*** Variables ***`
        # section and resources should be imported with `Resource` in the `*** Settings***` section
        return
    builtin = BuiltIn()
    for key, value in _suite_variables[item.path].items():
        builtin.set_suite_variable(r"${" + key + "}", value)
    for resource in _resources:
        import_resource(resource)


def pytest_runtestloop(session: Session) -> object:
    if session.config.option.collectonly:  # type:ignore[no-any-expr]
        return None
    # TODO: should probably keywordify skip as well, but it messes with the handling in robot_library
    # https://github.com/DetachHead/pytest-robotframework/issues/51
    for method in ("fail", "xfail", "raises", "deprecated_call", "warns"):
        keywordify(pytest, method)
    _collect_slash_run(session, collect_only=False)
    return True
