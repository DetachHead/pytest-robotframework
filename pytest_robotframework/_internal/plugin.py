"""the actual pytest plugin"""

from __future__ import annotations

from pathlib import Path

import pytest
from _pytest.main import resolve_collection_argument
from pluggy import Result
from pytest import Collector, StashKey, TempPathFactory, TestReport, hookimpl
from robot.api import logger
from robot.conf.settings import (
    RebotSettings,
    _BaseSettings,  # pyright:ignore[reportPrivateUsage]
)
from robot.libraries.BuiltIn import BuiltIn
from robot.output import LOGGER
from robot.rebot import Rebot
from robot.run import RobotFramework, RobotSettings
from typing_extensions import TYPE_CHECKING, Generator, Mapping, cast

from pytest_robotframework import (
    AssertOptions,
    Listener,
    RobotOptions,
    _hide_asserts_context_manager_key,  # pyright:ignore[reportPrivateUsage]
    _resources,  # pyright:ignore[reportPrivateUsage]
    _RobotClassRegistry,  # pyright:ignore[reportPrivateUsage]
    _suite_variables,  # pyright:ignore[reportPrivateUsage]
    as_keyword,
    hooks,
    import_resource,
    keywordify,
)
from pytest_robotframework._internal import cringe_globals
from pytest_robotframework._internal.errors import InternalError
from pytest_robotframework._internal.patches.pytest import explanation_key
from pytest_robotframework._internal.pytest_exception_getter import save_exception_to_item
from pytest_robotframework._internal.pytest_robot_items import RobotFile, RobotItem
from pytest_robotframework._internal.robot_classes import (
    AnsiLogger,
    ErrorDetector,
    PytestCollector,
    PytestRuntestProtocolHooks,
    PytestRuntestProtocolInjector,
    PythonParser,
)
from pytest_robotframework._internal.robot_utils import (
    banned_options,
    cli_defaults,
    escape_robot_str,
    merge_robot_options,
    report_robot_errors,
)
from pytest_robotframework._internal.xdist_utils import (
    is_xdist,
    is_xdist_master,
    is_xdist_worker,
    worker_id,
)

if TYPE_CHECKING:
    from pluggy import PluginManager
    from pytest import CallInfo, Item, Parser, Session

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
        / f"{worker_id(item.session)}_{hash(item.nodeid)}.xml"
    )


_robot_args_key = StashKey[RobotOptions]()


def _get_pytest_collection_paths(session: Session) -> set[Path]:
    """this is usually done during collection inside `perform_collect`, but since robot does the
    collection during `pytest_runtestloop we need to know these paths ahead of time.

    when pytest does this it returns a `list`, but we return a `set` instead because if there are
    any duplicates robot will incorrectly run the suite visitors/parsers/etc multiple times on the
    same suite"""
    # TODO: maybe refactor this so that collection always happens during the actual collection hooks
    # so this isn't needed.
    # https://github.com/DetachHead/pytest-robotframework/issues/189
    return {
        resolve_collection_argument(
            session.config.invocation_params.dir,
            arg,
            as_pypath=session.config.option.pyargs,  # pyright:ignore[reportAny]
        )[0]
        for arg in session.config.args
    }


def _get_robot_args(session: Session) -> RobotOptions:
    result: RobotOptions | None = session.stash.get(_robot_args_key, None)
    if result is not None:
        return result
    options: dict[str, object] = {}

    # set any robot options that were set in the pytest cli args:
    for arg_name, default_value in cli_defaults(RobotSettings).items():
        if arg_name in banned_options:
            continue
        options[arg_name] = cast(
            object,
            getattr(
                session.config.option,
                (
                    arg_name.replace("robot_no", "robot")
                    if isinstance(default_value, bool) and default_value
                    else f"robot_{arg_name}"
                ),
            ),
        )

    # parse any options from the ROBOT_OPTIONS variable:
    result = cast(
        RobotOptions,
        merge_robot_options(
            options,
            cast(
                RobotOptions,
                RobotFramework().parse_arguments(  # pyright:ignore[reportUnknownMemberType]
                    # i don't think this is actually used here, but we send it the correct paths
                    # just to be safe
                    _get_pytest_collection_paths(session)
                )[0],
            ),
        ),
    )
    session.config.hook.pytest_robot_modify_options(options=result, session=session)
    session.stash[_robot_args_key] = result
    return result


def _collect_or_run(
    session: Session,
    *,
    robot_options: RobotOptions,
    collect_only: bool,
    xdist_item: Item | None = None,
):
    """
    if not running with xdist:
    --------------------------
    this is called either by `pytest_collection` or `pytest_runtestloop` depending on whether
    `collect_only` is `True`, because to avoid having to run robot multiple times for both the
    collection and running, it's more efficient to just have `pytest_runtestloop` handle the
    collection as well if possible.

    if running with xdist:
    ----------------------
    this is called by `pytest_collection` to collect all the tests, then by
    `pytest_runtest_protocol` for each item individually. this means a separate robot session
    is started for every test.
    """
    # when running with xdist, collect/run gets called multiple times
    if not collect_only and not is_xdist(session) and _RobotClassRegistry.too_late:
        raise InternalError("somehow ran collect/run twice???")
    robot = RobotFramework()

    robot_args: Mapping[str, object] = merge_robot_options(
        robot_options,
        {
            "extension": "py:robot",
            "runemptysuite": True,
            "parser": [PythonParser(session)],
            "prerunmodifier": [
                PytestCollector(session, collect_only=collect_only, item=xdist_item)
            ],
        },
    )
    # needs to happen before collection cuz that's when the modules being keywordified get imported
    _keywordify_pytest_functions()
    if collect_only:
        robot_args = {
            **robot_args,
            "report": None,
            "output": None,
            "log": None,
            "exitonerror": True,
        }
    else:
        # we can't use our listener decorator here because we may have already set
        # _RobotClassRegistry.too_late to True
        listeners: list[Listener] = []
        # if item_context is not set then it's being run from pytest_runtest_protocol instead of
        # pytest_runtestloop so we don't need to re-implement pytest_runtest_protocol
        if xdist_item:
            robot_args = {
                **robot_args,
                "report": None,
                "log": None,
                "output": _log_path(xdist_item),
            }
        else:
            listeners.append(PytestRuntestProtocolHooks(session=session))
        listeners += [ErrorDetector(session=session, item=xdist_item), AnsiLogger()]
        robot_args = merge_robot_options(
            robot_args,
            {
                "prerunmodifier": [PytestRuntestProtocolInjector(session=session, item=xdist_item)],
                "listener": [*_RobotClassRegistry.listeners, *listeners],
                # we don't want prerebotmodifiers to run multiple times so we defer them to the end
                # of the test if we're running with xdist
                "prerebotmodifier": (
                    None if xdist_item else _RobotClassRegistry.pre_rebot_modifiers
                ),
            },
        )
    # technically it's not too late if running with xdist and it's only up to the collection stage,
    # but we don't want the errors to be dependent on whether the user is running with xdist or not.
    _RobotClassRegistry.too_late = True

    try:
        # LOGGER is needed for log_file listener methods to prevent logger from deactivating after
        # the test is over
        with LOGGER:
            _ = robot.main(  # pyright:ignore[reportUnknownMemberType,reportUnknownVariableType]
                _get_pytest_collection_paths(session),
                # needed because PythonParser.visit_init creates an empty suite
                **robot_args,
            )
    finally:
        # we don't want to clear listeners/pre_rebot_modifiers that were registered before
        # collection
        if not collect_only:
            _RobotClassRegistry.too_late = False

    robot_errors = report_robot_errors(session)
    if robot_errors:
        raise Exception(robot_errors)


def pytest_addhooks(pluginmanager: PluginManager):
    pluginmanager.add_hookspecs(hooks)


def pytest_addoption(parser: Parser):
    group = parser.getgroup(
        "robot",
        "robotframework (if an option is missing, it means there's a pytest equivalent you should"
        + "use instead. see https://github.com/DetachHead/pytest-robotframework#config)",
    )
    group.addoption(
        "--no-assertions-in-robot-log",
        dest="assertions_in_robot_log",
        default=True,
        action="store_false",
        help="whether to hide passing `assert` statements in the robot log by default. when this is"
        + " disabled, you can make individual `assert` statements show in the log using the"
        + " `pytest_robotframework.AssertionOptions` class with `log_pass=True`. see the docs for"
        + " more information: https://github.com/DetachHead/pytest-robotframework/tree/assertion-ricing#hiding-non-user-facing-assertions",
    )
    for arg_name, default_value in cli_defaults(RobotSettings).items():
        if arg_name in banned_options:
            continue
        arg_name_with_prefix = f"--robot-{arg_name}"
        if isinstance(default_value, bool):
            if default_value:
                group.addoption(
                    f"--robot-no{arg_name}",
                    dest=arg_name,
                    default=default_value,
                    action="store_false",
                )
            else:
                group.addoption(arg_name_with_prefix, default=default_value, action="store_true")
        else:
            group.addoption(
                arg_name_with_prefix,
                default=default_value,
                action="append" if isinstance(default_value, list) else None,
                help=(
                    None
                    if default_value is None
                    or (isinstance(default_value, list) and not default_value)
                    else f"default: {default_value}"
                ),
            )


@hookimpl(tryfirst=True)
def pytest_sessionstart(session: Session):
    cringe_globals._current_session = session  # pyright:ignore[reportPrivateUsage]


@hookimpl(wrapper=True, tryfirst=True)
def pytest_sessionfinish(session: Session) -> HookWrapperResult:
    try:
        if not session.config.option.collectonly and is_xdist_master(  # pyright:ignore[reportAny]
            session
        ):
            robot_args = _get_robot_args(session=session)

            def option_names(settings: Mapping[str, tuple[str, object]]) -> list[str]:
                return [value[0] for value in settings.values()]

            outputs = list(_xdist_temp_dir(session).glob("*/robot_xdist_outputs/*.xml"))
            # if there were no outputs there were probably no tests run or some other error occured,
            # so silently skip this
            if outputs:
                Rebot().main(  # pyright:ignore[reportUnusedCallResult,reportUnknownMemberType]
                    outputs,
                    # merge is deliberately specified here instead of in the merged dict because it
                    # should never be overwritten
                    merge=True,
                    **merge_robot_options(
                        {
                            # rebot doesn't recreate the output.xml unless you sepecify it
                            # explicitly. we want to do this because our usage of rebot is an
                            # implementation detail and we want the output to appear the same
                            # regardless of whether the user is running with xdist
                            "output": "output.xml",
                            "prerebotmodifier": _RobotClassRegistry.pre_rebot_modifiers,
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
    finally:
        _RobotClassRegistry.listeners.clear()
        _RobotClassRegistry.pre_rebot_modifiers.clear()
        cringe_globals._current_session = None  # pyright:ignore[reportPrivateUsage]


def pytest_assertion_pass(item: Item, expl: str):
    """getting the explanation from this hook to pass on to the `pytest_robot_assertion` hook"""
    item.stash[explanation_key] = expl


def pytest_robot_assertion(
    item: Item,
    expression: str,
    fail_message: object,
    explanation: str,
    assertion_error: AssertionError | None,
):
    show_in_log: bool | None = None
    # we always want to show the assertion if it failed:
    if assertion_error:
        show_in_log = True
    if isinstance(fail_message, AssertOptions):
        if not assertion_error and fail_message.log_pass is not None:
            show_in_log = fail_message.log_pass
        description = fail_message.description
    else:
        description = None
    if show_in_log is None:
        show_in_log = (
            item.config.option.assertions_in_robot_log  # pyright:ignore[reportAny]
            and not item.stash.get(_hide_asserts_context_manager_key, False)
        )
    if show_in_log:
        with as_keyword("assert", args=[expression if description is None else description]):
            if description is not None:
                # the original expression was overwritten so we log it here instead
                logger.info(f"assert {expression}")
            if assertion_error:
                raise assertion_error
            logger.info(explanation)


def pytest_runtest_makereport(item: Item, call: CallInfo[None]) -> TestReport | None:
    late_failures = report_robot_errors(item)
    if late_failures:
        result = TestReport.from_item_and_call(item, call)
        result.outcome = "failed"
        result.longrepr = (f"{result.longrepr}\n\n" if result.longrepr else "") + late_failures
        return result
    return None


def pytest_collection(session: Session) -> object:
    robot_args = _get_robot_args(session=session)
    if session.config.option.collectonly or is_xdist_worker(  # pyright:ignore[reportAny]
        session
    ):
        _collect_or_run(session, collect_only=True, robot_options=robot_args)
    return True


def pytest_collect_file(parent: Collector, file_path: Path) -> Collector | None:
    if file_path.suffix == ".robot":
        return cast(
            Collector,
            RobotFile.from_parent(  # pyright:ignore[reportUnknownMemberType]
                parent, path=file_path
            ),
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
                r"${" + key + "}", escape_robot_str(value) if isinstance(value, str) else value
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


def _keywordify_pytest_functions():
    # we change the module since these methods get re-exported from pytest but are actually defined
    # in a gross looking internal `_pytest` module
    module = "pytest"
    # TODO: should probably keywordify skip as well, but it messes with the handling in
    # robot_library
    # https://github.com/DetachHead/pytest-robotframework/issues/51
    for method in ("fail", "xfail"):
        keywordify(pytest, method, module=module)
    for method in ("deprecated_call", "warns", "raises"):
        keywordify(pytest, method, wrap_context_manager=True, module=module)


@hookimpl(tryfirst=True)
def pytest_runtestloop(session: Session) -> object:
    if (
        session.config.option.collectonly  # pyright:ignore[reportAny]
        # if we're running with xdist, we can't replace the runtestloop with our own because it
        # conflicts with xdist's one. instead we need to run robot individually on each test (in
        # pytest_runtest_protocol) since we can't know which tests we need to run ahead of time (i
        # think they can dynamically change mid session)
        or is_xdist_master(session)
        # however if we're in a worker and there are no items, that means there are no items in the
        # whole session (i hope). in which case we still need to run robot here to generate an empty
        # log, because pytest_runtest_protocol never gets called if there's no items but we still
        # want a log anyway cuz that's how robot normally behaves
        or (is_xdist_worker(session) and session.items)
    ):
        return None
    robot_args = _get_robot_args(session=session)
    _collect_or_run(session, collect_only=False, robot_options=robot_args)
    return None if is_xdist(session) else True


@hookimpl(tryfirst=True)
def pytest_runtest_protocol(item: Item):
    if is_xdist_worker(item.session):
        _collect_or_run(
            item.session,
            collect_only=False,
            xdist_item=item,
            robot_options=_get_robot_args(session=item.session),
        )
        return True
    return None
