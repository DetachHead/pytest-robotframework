"""the actual pytest plugin"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Generator, cast

import pytest
from deepmerge import always_merger
from pluggy import Result
from pytest import TestReport, hookimpl
from robot.api import logger
from robot.conf.settings import _BaseSettings
from robot.libraries.BuiltIn import BuiltIn
from robot.output import LOGGER
from robot.run import RobotFramework
from robot.utils import abspath

from pytest_robotframework import (
    _resources,
    _RobotClassRegistry,
    _suite_variables,
    as_keyword,
    import_resource,
    keywordify,
    listener,
)
from pytest_robotframework._internal import cringe_globals, hooks
from pytest_robotframework._internal.errors import InternalError
from pytest_robotframework._internal.pytest_exception_getter import (
    save_exception_to_item,
)
from pytest_robotframework._internal.pytest_robot_items import RobotFile, RobotItem
from pytest_robotframework._internal.robot_classes import (
    ErrorDetector,
    PytestCollector,
    PytestRuntestProtocolHooks,
    PytestRuntestProtocolInjector,
    PythonParser,
)
from pytest_robotframework._internal.robot_utils import (
    escape_robot_str,
    report_robot_errors,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pluggy import PluginManager
    from pytest import CallInfo, Collector, Item, Parser, Session

HookImplResult = Generator[None, Result[object], None]


def _collect_slash_run(session: Session, *, collect_only: bool):
    """this is called either by `pytest_collection` or `pytest_runtestloop` depending on whether
    `collect_only` is `True`, because to avoid having to run robot multiple times for both the
    collection and running, it's more efficient to just have `pytest_runtestloop` handle the
    collection as well if possible.
    """
    if _RobotClassRegistry.too_late:
        raise InternalError("somehow ran collect/run twice???")
    robot = RobotFramework()  # type:ignore[no-untyped-call]

    # need to reset outputdir because if anything from robot gets imported before pytest runs, then
    # the cwd gets updated, robot will still run with the outdated cwd.
    # we set it in this wacky way to make sure it never overrides user preferences
    _BaseSettings._cli_opts[  # type:ignore[no-untyped-usage,no-any-expr] # noqa: SLF001
        "OutputDir"
    ] = (  # type:ignore[no-any-expr]
        "outputdir",
        abspath("."),  # type:ignore[no-untyped-call,no-any-expr]
    )

    robot_arg_list: list[str] = []
    session.config.hook.pytest_robot_modify_args(
        args=robot_arg_list, session=session, collect_only=collect_only
    )
    robot_args = cast(
        Dict[str, object],
        always_merger.merge(  # type:ignore[no-untyped-call]
            # https://github.com/psf/black/issues/4036
            # fmt:off
            robot.parse_arguments(  # type:ignore[no-untyped-call]
                [  # type:ignore[no-any-expr]
                    *robot_arg_list,
                    # not actually used here, but the argument parser requires at least one path
                    session.path,
                ]
            )[0],
            # fmt:on
            {  # type:ignore[no-any-expr]
                "extension": "py:robot",
                "runemptysuite": True,
                "parser": [PythonParser(session)],  # type:ignore[no-any-expr]
                "prerunmodifier": [  # type:ignore[no-any-expr]
                    PytestCollector(session, collect_only=collect_only)
                ],
            }
        ),
    )
    if collect_only:
        robot_args = {
            **robot_args,
            "report": None,
            "output": None,
            "log": None,
            "exitonerror": True,
        }
    else:
        listener(PytestRuntestProtocolHooks(session))
        listener(ErrorDetector(session))
        robot_args = always_merger.merge(  # type:ignore[no-untyped-call]
            robot_args,
            {  # type:ignore[no-any-expr]
                "prerunmodifier": [  # type:ignore[no-any-expr]
                    PytestRuntestProtocolInjector(session)
                ],
                "listener": _RobotClassRegistry.listeners,
                "prerebotmodifier": _RobotClassRegistry.pre_rebot_modifiers,
            },
        )
    _RobotClassRegistry.too_late = True

    try:
        # LOGGER is needed for log_file listener methods to prevent logger from deactivating after
        # the test is over
        with LOGGER:
            robot.main(  # type:ignore[no-untyped-call]
                [session.path],  # type:ignore[no-any-expr]
                # needed because PythonParser.visit_init creates an empty suite
                **robot_args,
            )
    finally:
        _RobotClassRegistry.reset()

    robot_errors = report_robot_errors(session)
    if robot_errors:
        raise Exception(robot_errors)


def pytest_addhooks(pluginmanager: PluginManager):
    pluginmanager.add_hookspecs(hooks)


_robotargs_deprecation_msg = (
    "use a `pytest_robot_modify_args` hook or set the `ROBOT_OPTIONS` environment"
    " variable instead"
)


def pytest_addoption(parser: Parser):
    parser.addoption(
        "--robotargs",
        default="",
        help=(
            "additional arguments to be passed to robotframework (deprecated:"
            f" {_robotargs_deprecation_msg})"
        ),
    )


def pytest_robot_modify_args(args: list[str], session: Session):
    result = cast(
        str,
        session.config.getoption(  # type:ignore[no-untyped-call]
            "--robotargs"
        ),
    )
    if result:
        # i saw some code that uses session.config.issue_config_time_warning but that doesnt work
        # who knows why
        print(  # noqa: T201
            f"\n`--robotargs` is deprecated (received {result!r}). specifying arguments"
            " via the command line is unreliable because CLIs suck."
            f" {_robotargs_deprecation_msg}"
        )
    args.extend(result.split(" "))


@hookimpl(tryfirst=True)  # type:ignore[no-any-expr]
def pytest_sessionstart(session: Session):
    cringe_globals._current_session = session  # noqa: SLF001


@hookimpl(trylast=True)  # type:ignore[no-any-expr]
def pytest_sessionfinish():
    cringe_globals._current_session = None  # noqa: SLF001


def pytest_assertion_pass(orig: str, expl: str):
    """without this hook, passing assertions won't show up at all in the robot log"""
    # this matches what's logged if an assertion fails, so we keep it the same here for consistency
    # (idk why there's no pytest_assertion_fail hook, only reprcompare which is different)
    with as_keyword("assert", args=[orig]):
        logger.info(expl)  # type:ignore[no-untyped-call]


def pytest_runtest_makereport(item: Item, call: CallInfo[None]) -> TestReport | None:
    late_failures = report_robot_errors(item)
    if late_failures:
        result = TestReport.from_item_and_call(item, call)
        result.outcome = "failed"
        result.longrepr = (
            f"{result.longrepr}\n\n" if result.longrepr else ""
        ) + late_failures
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


@hookimpl(hookwrapper=True)  # type:ignore[no-any-expr]
def pytest_runtest_setup(item: Item) -> HookImplResult:
    if not isinstance(item, RobotItem):
        # `set_variables` and `import_resource` is only supported in python files.
        # when running robot files, suite variables should be set using the `*** Variables ***`
        # section and resources should be imported with `Resource` in the `*** Settings***` section
        builtin = BuiltIn()
        for key, value in _suite_variables[item.path].items():
            builtin.set_suite_variable(
                r"${" + key + "}",
                escape_robot_str(value) if isinstance(value, str) else value,
            )
        del _suite_variables[item.path]
        for resource in _resources:
            import_resource(resource)
    result = yield
    save_exception_to_item(item, result)


@hookimpl(hookwrapper=True)  # type:ignore[no-any-expr]
def pytest_runtest_call(item: Item) -> HookImplResult:
    result = yield
    save_exception_to_item(item, result)


@hookimpl(hookwrapper=True)  # type:ignore[no-any-expr]
def pytest_runtest_teardown(item: Item) -> HookImplResult:
    result = yield
    save_exception_to_item(item, result)


def pytest_runtestloop(session: Session) -> object:
    if session.config.option.collectonly:  # type:ignore[no-any-expr]
        return None
    # TODO: should probably keywordify skip as well, but it messes with the handling in robot_library
    # https://github.com/DetachHead/pytest-robotframework/issues/51
    for method in ("fail", "xfail"):
        keywordify(pytest, method)
    for method in ("deprecated_call", "warns", "raises"):
        keywordify(pytest, method, wrap_context_manager=True)
    _collect_slash_run(session, collect_only=False)
    return True
