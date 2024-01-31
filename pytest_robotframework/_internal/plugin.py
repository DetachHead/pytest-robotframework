"""the actual pytest plugin"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Generator, Mapping, cast

import pytest
from pluggy import Result
from pytest import StashKey, TempPathFactory, TestReport, hookimpl
from robot.api import logger
from robot.conf.settings import (
    RebotSettings,
    _BaseSettings,  # pyright:ignore[reportPrivateUsage]
)
from robot.libraries.BuiltIn import BuiltIn
from robot.output import LOGGER
from robot.rebot import Rebot
from robot.run import RobotFramework
from robot.utils import abspath  # pyright:ignore[reportUnknownVariableType]

from pytest_robotframework import (
    _resources,  # pyright:ignore[reportPrivateUsage]
    _RobotClassRegistry,  # pyright:ignore[reportPrivateUsage]
    _suite_variables,  # pyright:ignore[reportPrivateUsage]
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
    RobotArgs,
    escape_robot_str,
    merge_robot_options,
    report_robot_errors,
)
from pytest_robotframework._internal.xdist_utils import (
    JobInfo,
    is_xdist,
    is_xdist_master,
    is_xdist_worker,
    worker_id,
)

if TYPE_CHECKING:

    from pluggy import PluginManager
    from pytest import CallInfo, Collector, Item, Parser, Session

HookWrapperResult = Generator[None, Result[object], None]


def _xdist_temp_dir(session: Session) -> Path:
    return Path(
        cast(
            TempPathFactory,
            session.config._tmp_path_factory,  # pyright:ignore[reportUnknownMemberType,reportAttributeAccessIssue]
        ).getbasetemp()
    )


def _log_path(item: Item) -> Path:
    return (
        _xdist_temp_dir(item.session)
        / "robot_xdist_outputs"
        / f"{worker_id(item.session)}_{hash(item.name)}.xml"
    )


_robot_args_key = StashKey[RobotArgs]()


def _get_robot_args(session: Session, *, collect_only: bool) -> RobotArgs:
    result = session.stash.get(_robot_args_key, None)
    if result is not None:
        return result
    # need to reset outputdir because if anything from robot gets imported before pytest runs, then
    # the cwd gets updated, robot will still run with the outdated cwd.
    # we set it in this wacky way to make sure it never overrides user preferences
    _BaseSettings._cli_opts[  # pyright:ignore[reportUnknownMemberType,reportPrivateUsage]
        "OutputDir"
    ] = (
        "outputdir",
        abspath("."),
    )
    robot_arg_list: list[str] = []
    session.config.hook.pytest_robot_modify_args(
        args=robot_arg_list, session=session, collect_only=collect_only
    )
    result = cast(
        RobotArgs,
        RobotFramework().parse_arguments([  # pyright:ignore[reportUnknownMemberType]
            *robot_arg_list,
            # not actually used here, but the argument parser requires at least one path
            session.startpath,
        ])[0],
    )
    session.stash[_robot_args_key] = result
    return result


def _collect_or_run(
    session: Session,
    *,
    robot_args: RobotArgs,
    collect_only: bool,
    job: JobInfo | None = None,
):
    """this is called either by `pytest_collection` or `pytest_runtestloop` depending on whether
    `collect_only` is `True`, because to avoid having to run robot multiple times for both the
    collection and running, it's more efficient to just have `pytest_runtestloop` handle the
    collection as well if possible.
    """
    if _RobotClassRegistry.too_late:
        raise InternalError("somehow ran collect/run twice???")
    item = job.item if job else None
    robot = RobotFramework()

    robot_args = merge_robot_options(
        robot_args,
        {
            "extension": "py:robot",
            "runemptysuite": True,
            "parser": [PythonParser(session)],
            "prerunmodifier": [
                PytestCollector(session, collect_only=collect_only, item=item)
            ],
        },
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
        _keywordify()
        # if item_context is not set then it's being run from pytest_runtest_protocol instead of
        # pytest_runtestloop so we don't need to re-implement pytest_runtest_protocol
        if job:
            robot_args = {
                **robot_args,
                "report": None,
                "log": None,
                "output": _log_path(job.item),
            }
        else:
            _ = listener(PytestRuntestProtocolHooks(session=session, item=item))
        _ = listener(ErrorDetector(session=session, item=item))
        robot_args = merge_robot_options(
            robot_args,
            {
                "prerunmodifier": [
                    PytestRuntestProtocolInjector(session=session, item_context=job)
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
            _ = robot.main(  # pyright:ignore[reportUnknownMemberType,reportUnknownVariableType]
                [session.startpath],
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
    result = cast(str, session.config.getoption("--robotargs"))
    if result:
        # i saw some code that uses session.config.issue_config_time_warning but that doesnt work
        # who knows why
        print(  # noqa: T201
            f"\n`--robotargs` is deprecated (received {result!r}). specifying arguments"
            " via the command line is unreliable because CLIs suck."
            f" {_robotargs_deprecation_msg}"
        )
    args.extend(result.split(" "))


@hookimpl(tryfirst=True)
def pytest_sessionstart(session: Session):
    cringe_globals._current_session = session  # pyright:ignore[reportPrivateUsage]


@hookimpl(wrapper=True, tryfirst=True)
def pytest_sessionfinish(session: Session) -> HookWrapperResult:
    if not session.config.option.collectonly and is_xdist_master(session):
        robot_args = _get_robot_args(session=session, collect_only=False)

        def option_names(settings: Mapping[str, tuple[str, object]]) -> list[str]:
            return [value[0] for value in settings.values()]

        Rebot().main(  # pyright:ignore[reportUnusedCallResult,reportUnknownMemberType]
            _xdist_temp_dir(session).glob("*/robot_xdist_outputs/*.xml"),
            # merge is deliberately specified here instead of in the merged dict because it should
            # never be overwritten
            merge=True,
            **merge_robot_options(
                {
                    # rebot doesn't recreate the output.xml unless you sepecify it explicitly. we
                    # want to do this because our usage of rebot is an implementation detail and we
                    # want the output to appear the same regardless of whether the user is running
                    # with xdist
                    "output": "output.xml"
                },
                {
                    key: value
                    for key, value in robot_args.items()
                    if key
                    in option_names(
                        RebotSettings._extra_cli_opts  # pyright:ignore[reportPrivateUsage]
                    )
                    or key
                    in option_names(
                        _BaseSettings._cli_opts  # pyright:ignore[reportPrivateUsage,reportUnknownArgumentType,reportUnknownMemberType]
                    )
                },
            ),
        )
    yield
    cringe_globals._current_session = None  # pyright:ignore[reportPrivateUsage]


def pytest_assertion_pass(orig: str, expl: str):
    """without this hook, passing assertions won't show up at all in the robot log"""
    # this matches what's logged if an assertion fails, so we keep it the same here for consistency
    # (idk why there's no pytest_assertion_fail hook, only reprcompare which is different)
    with as_keyword("assert", args=[orig]):
        logger.info(expl)


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
    collect_only = session.config.option.collectonly
    robot_args = _get_robot_args(session=session, collect_only=collect_only)
    if collect_only or is_xdist_worker(session):
        _collect_or_run(session, collect_only=True, robot_args=robot_args)
    return True


def pytest_collect_file(parent: Collector, file_path: Path) -> Collector | None:
    if file_path.suffix == ".robot":
        return RobotFile.from_parent(  # pyright:ignore[reportUnknownMemberType]
            parent, path=file_path
        )
    return None


@hookimpl(hookwrapper=True)
def pytest_runtest_setup(item: Item) -> HookWrapperResult:
    if not isinstance(item, RobotItem):
        # `set_variables` and `import_resource` is only supported in python files.
        # when running robot files, suite variables should be set using the `*** Variables ***`
        # section and resources should be imported with `Resource` in the `*** Settings***` section
        builtin = BuiltIn()
        for key, value in _suite_variables[item.path].items():
            builtin.set_suite_variable(  # pyright:ignore[reportUnknownMemberType]
                r"${" + key + "}",
                escape_robot_str(value) if isinstance(value, str) else value,
            )
        del _suite_variables[item.path]
        for resource in _resources:
            import_resource(resource)
    result = yield
    save_exception_to_item(item, result)


@hookimpl(hookwrapper=True)
def pytest_runtest_call(item: Item) -> HookWrapperResult:
    result = yield
    save_exception_to_item(item, result)


@hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item: Item) -> HookWrapperResult:
    result = yield
    save_exception_to_item(item, result)


def _keywordify():
    # TODO: should probably keywordify skip as well, but it messes with the handling in robot_library
    # https://github.com/DetachHead/pytest-robotframework/issues/51
    for method in ("fail", "xfail"):
        keywordify(pytest, method)
    for method in ("deprecated_call", "warns", "raises"):
        keywordify(pytest, method, wrap_context_manager=True)


@hookimpl(tryfirst=True)
def pytest_runtestloop(session: Session) -> object:
    if session.config.option.collectonly or is_xdist(session):
        # we can't rice the runtest protocol because xdist already does. so we need to run robot
        # individually on each test (in pytest_runtest_protocol) since we can't know which tests
        # we need to run ahead of time (i think they can dynamically change mid session)
        # Rebot.
        return None
    robot_args = _get_robot_args(session=session, collect_only=False)
    _collect_or_run(session, collect_only=False, robot_args=robot_args)
    return True


@hookimpl(tryfirst=True)
def pytest_runtest_protocol(item: Item, nextitem: Item | None):
    if is_xdist_worker(item.session):
        _collect_or_run(
            item.session,
            collect_only=False,
            job=JobInfo(
                item=item, nextitem=nextitem, temp_dir=_xdist_temp_dir(item.session)
            ),
            robot_args=_get_robot_args(session=item.session, collect_only=False),
        )
        return True
    return None
