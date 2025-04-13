"""the actual pytest plugin"""

from __future__ import annotations

import contextlib
import os
from ast import Assert, Call, Constant, Expr, If, Raise, copy_location, stmt
from pathlib import Path
from typing import IO

import pytest
from _pytest.assertion import rewrite
from _pytest.assertion.rewrite import (
    AssertionRewriter,
    _get_assertion_exprs,  # pyright:ignore[reportPrivateUsage]
    traverse_node,
)
from _pytest.main import resolve_collection_argument
from pytest import (
    Collector,
    Config,
    StashKey,
    TempPathFactory,
    TestReport,
    hookimpl,
    skip,
    version_tuple as pytest_version,
)
from robot.api import logger
from robot.conf.settings import (
    RebotSettings,
    _BaseSettings,  # pyright:ignore[reportPrivateUsage]
)
from robot.libraries.BuiltIn import BuiltIn
from robot.output import LOGGER
from robot.rebot import Rebot
from robot.result.resultbuilder import ExecutionResult
from robot.run import RobotFramework, RobotSettings
from robot.utils.error import ErrorDetails
from typing_extensions import TYPE_CHECKING, Callable, Generator, Mapping, cast

from pytest_robotframework import (
    AssertOptions,
    Listener,
    RobotOptions,
    _hide_asserts_context_manager_key,  # pyright:ignore[reportPrivateUsage]
    _resources,  # pyright:ignore[reportPrivateUsage]
    _suite_variables,  # pyright:ignore[reportPrivateUsage]
    as_keyword,
    hooks,
    import_resource,
    keywordify,
)
from pytest_robotframework._internal import cringe_globals
from pytest_robotframework._internal.cringe_globals import current_item
from pytest_robotframework._internal.errors import InternalError
from pytest_robotframework._internal.pytest.exception_getter import exception_key
from pytest_robotframework._internal.pytest.robot_file_support import RobotFile, RobotItem
from pytest_robotframework._internal.pytest.xdist_utils import (
    is_xdist,
    is_xdist_master,
    is_xdist_worker,
    worker_id,
)
from pytest_robotframework._internal.robot.listeners_and_suite_visitors import (
    AnsiLogger,
    ErrorDetector,
    PytestRuntestProtocolHooks,
    PytestRuntestProtocolInjector,
    PythonParser,
    RobotSuiteCollector,
    RobotTestFilterer,
)
from pytest_robotframework._internal.robot.utils import (
    InternalRobotOptions,
    banned_options,
    cli_defaults,
    escape_robot_str,
    is_robot_traceback,
    merge_robot_options,
    report_robot_errors,
    robot_6,
)
from pytest_robotframework._internal.utils import patch_method

if TYPE_CHECKING:
    from types import TracebackType

    from _pytest.terminal import TerminalReporter
    from pluggy import PluginManager
    from pytest import CallInfo, Item, Parser, Session


_explanation_key = StashKey[str]()


def _call_assertion_hook(
    expression: str,
    fail_message: object,
    line_number: int,
    assertion_error: AssertionError | None,
    explanation: str | None = None,
):
    item = current_item()
    if not item:
        return
    if assertion_error and explanation and explanation.startswith("\n"):
        # pretty gross but we have to remove this trailing \n which means the fail message was None
        # but the assertion rewriter already wrote the error message thinking it wasn't None because
        # it was an AssertOptions object
        explanation = explanation[1:]
        assertion_error.args = (explanation, *assertion_error.args[1:])
    item.ihook.pytest_robot_assertion(
        item=item,
        expression=expression,
        fail_message=fail_message,
        line_number=line_number,
        assertion_error=assertion_error,
        explanation=item.stash[_explanation_key] if explanation is None else explanation,
    )


# we aren't patching an existing function here but instead adding a new one to the rewrite module,
# since the rewritten assert statement needs to call it, and this is the easist way to do that
rewrite._call_assertion_hook = _call_assertion_hook  # pyright:ignore[reportAttributeAccessIssue]


@patch_method(AssertionRewriter)
def visit_Assert(  # noqa: N802
    og: Callable[[AssertionRewriter, Assert], list[stmt]], self: AssertionRewriter, assert_: Assert
) -> list[stmt]:
    """
    we patch the assertion rewriter because the hook functions do not give us what we need. see
    these issues:

    - https://github.com/pytest-dev/pytest/issues/11984
    - https://github.com/pytest-dev/pytest/issues/11975
    """
    result = og(self, assert_)
    if not self.enable_assertion_pass_hook:
        return result
    assert_msg = assert_.msg or Constant(None)
    if not self.config:
        raise InternalError("failed to rewrite assertion because config was somehow `None`")
    try:
        main_test = next(statement for statement in reversed(result) if isinstance(statement, If))
    except StopIteration:
        raise InternalError("failed to find if statement for assertion rewriting") from None
    expression = _get_assertion_exprs(self.source)[assert_.lineno]
    # rice the fail statements:
    raise_statement = cast(Raise, main_test.body.pop())
    if not raise_statement.exc:
        raise InternalError("raise statement without exception")
    main_test.body.append(
        Expr(
            self.helper(
                "_call_assertion_hook",
                Constant(expression),  # expression
                assert_msg,  # fail_message
                Constant(assert_.lineno),  # line_number
                raise_statement.exc,  # assertion_error
                cast(Call, raise_statement.exc).args[0],  # explanation
            )
        )
    )

    # rice the pass statements:
    main_test.orelse.append(
        Expr(
            self.helper(
                "_call_assertion_hook",
                Constant(expression),  # expression
                assert_msg,  # fail_message
                Constant(assert_.lineno),  # line_number
                Constant(None),  # assertion_error
                # explanation is handled by the pytest_assertion_pass hook above, since its too
                # hard to get it from here
            )
        )
    )
    # copied from the end of og, need to rerun this since a new statement was added:
    for statement in result:
        for node in traverse_node(statement):
            _ = copy_location(node, assert_)
    return result


HookWrapperResult = Generator[None, object, None]


def _xdist_temp_dir(session: Session) -> Path:
    return Path(
        cast(
            TempPathFactory,
            session.config._tmp_path_factory,  # pyright:ignore[reportAttributeAccessIssue]
        ).getbasetemp()
    )


_xdist_ourput_dir_name = "robot_xdist_outputs"


def _get_pytest_collection_paths(session: Session) -> frozenset[Path]:
    """
    this is usually done during collection inside `perform_collect`,
    but there's a "circular dependency" between pytest collection and robot "collection":
    pytest collection needs the tests collected by robot, but for robot to run it needs the paths
    resolved during pytest collection.
    """
    if session._initialpaths:  # pyright:ignore[reportPrivateUsage]
        return session._initialpaths  # pyright:ignore[reportPrivateUsage]
    result: set[Path] = set()
    for arg in session.config.args:
        collection_argument = resolve_collection_argument(
            session.config.invocation_params.dir,
            arg,
            as_pypath=session.config.option.pyargs,  # pyright:ignore[reportAny]
        )
        path = (
            collection_argument.path
            if pytest_version >= (8, 1)
            # we only run pyright on pytest >=8.1
            else cast(Path, collection_argument[0])  # pyright:ignore[reportIndexIssue]
        )
        result.add(path)
    return frozenset(result)


_robot_args_key = StashKey[RobotOptions]()


def _get_robot_args(session: Session) -> RobotOptions:
    result = session.config.stash.get(_robot_args_key, None)
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
    options = merge_robot_options(
        options,
        cast(
            RobotOptions,
            RobotFramework().parse_arguments(
                # i don't think this is actually used here, but we send it the correct paths
                # just to be safe
                _get_pytest_collection_paths(session)
            )[0],
        ),
    )
    # https://github.com/DetachHead/basedpyright#note-about-casting-with-typeddicts
    result = cast(RobotOptions, options)  # pyright:ignore[reportInvalidCast]
    session.config.hook.pytest_robot_modify_options(options=result, session=session)
    session.config.stash[_robot_args_key] = result
    return result


def _run_robot(session: Session, robot_options: InternalRobotOptions):
    """runs robot with the specified `robot_options`"""
    robot_options = merge_robot_options(
        # user-specified options:
        _get_robot_args(session),
        # collect or run test specific options:
        robot_options,
        # options that always need to be set:
        {"runemptysuite": True},
    )

    # listener gets set to None in collection when we want to override user-defined preferences, but
    # robot 6 doesn't support that
    if robot_6 and robot_options["listener"] is None:
        robot_options["listener"] = []

    robot = RobotFramework()
    # LOGGER is needed for log_file listener methods to prevent logger from deactivating after
    # the test is over
    with LOGGER:
        exit_code = robot.main(
            _get_pytest_collection_paths(session),
            # needed because PythonParser.visit_init creates an empty suite
            **robot_options,
        )

    robot_errors = report_robot_errors(session)
    if robot_errors:
        raise Exception(robot_errors)
    if exit_code and not session.testsfailed:
        raise Exception(
            f"pytest-robotframework detected that robot failed with exit code {exit_code} despite"
            " no tests failing. this may have been caused by a robot error that occurred"
            " before any tests started."
        )


def _robot_collect(session: Session):
    """
    runs robot in "collection" mode, meaning it won't actually run any tests or output any result
    files. this is only used to set `session.stash[collected_robot_tests_key]` which is then used in
    `_internal.pytest.robot_file_support` during collectionto create `RobotItem`s for tests located
    in `.robot` files
    """
    robot_options = {
        "report": None,
        "output": None,
        "log": None,
        "exitonerror": True,
        "prerunmodifier": [RobotSuiteCollector(session)],
        "listener": None,
        "console": "none",
    }
    _run_robot(session, robot_options)


def _robot_run_tests(session: Session, xdist_item: Item | None = None):
    """
    runs robot either on an individual item or on every item in the session.

    :param xdist_item: if provided, only runs robot for this item.
    """
    items = [xdist_item] if xdist_item else session.items
    robot_options: InternalRobotOptions = {"parser": [PythonParser(items)], "extension": "py:robot"}
    listeners: list[Listener] = [ErrorDetector(session=session, item=xdist_item), AnsiLogger()]
    if not robot_6:
        # this listener is conditionally defined so has to be conditionally imported
        from pytest_robotframework._internal.robot.listeners_and_suite_visitors import (  # noqa: PLC0415
            KeywordUnwrapper,
        )

        listeners.append(KeywordUnwrapper())
    robot_options = merge_robot_options(
        robot_options,
        {
            "prerunmodifier": [
                RobotTestFilterer(session, items=items),
                PytestRuntestProtocolInjector(session=session, xdist_item=xdist_item),
            ],
            "listener": listeners,
        },
    )
    # if xdist_item is not set then it's being run from pytest_runtest_protocol instead of
    # pytest_runtestloop so we don't need to re-implement pytest_runtest_protocol
    if xdist_item:
        robot_options = merge_robot_options(
            robot_options,
            {
                "report": None,
                "log": None,
                "output": str(
                    _xdist_temp_dir(xdist_item.session)
                    / _xdist_ourput_dir_name
                    / f"{worker_id(xdist_item.session)}_{hash(xdist_item.nodeid)}.xml"
                ),
                # we don't want prerebotmodifiers to run multiple times so we defer them to the end
                # of the test if we're running with xdist
                "prerebotmodifier": None,
            },
        )
    else:
        listeners.append(PytestRuntestProtocolHooks(session=session))
    _ = _run_robot(session, robot_options)


def pytest_addhooks(pluginmanager: PluginManager):
    pluginmanager.add_hookspecs(hooks)


def pytest_addoption(parser: Parser):
    group = parser.getgroup(
        "robot",
        "robotframework (if an option is missing, it means there's a pytest equivalent you should"
        "use instead. see https://github.com/DetachHead/pytest-robotframework#config)",
    )
    group.addoption(
        "--no-assertions-in-robot-log",
        dest="assertions_in_robot_log",
        default=True,
        action="store_false",
        help="whether to hide passing `assert` statements in the robot log by default. when this is"
        " disabled, you can make individual `assert` statements show in the log using the"
        " `pytest_robotframework.AssertionOptions` class with `log_pass=True`. see the docs for"
        " more information: https://github.com/DetachHead/pytest-robotframework/tree/assertion-ricing#hiding-non-user-facing-assertions",
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
    _keywordify_pytest_functions()
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

            outputs = list(_xdist_temp_dir(session).glob(f"*/{_xdist_ourput_dir_name}/*.xml"))
            # if there were no outputs there were probably no tests run or some other error occured,
            # so silently skip this
            if outputs:

                def redirector(file: IO[str]) -> contextlib._RedirectStream[IO[str]]:  # pyright: ignore[reportPrivateUsage]
                    # Here we create a jenkem huffer because you can't control rebots console output
                    #  Rebot uses __stdout__, which doesn't have an implementation in contextlib
                    result = contextlib._RedirectStream(file)  # pyright: ignore[reportPrivateUsage]
                    result._stream = "__stdout__"  # pyright: ignore[reportAttributeAccessIssue]
                    return result

                with Path(os.devnull).open("w", encoding="UTF8") as devull, redirector(devull):
                    rebot = Rebot()
                    # if tests from different suites were run, the top level suite can have a
                    # different name. rebot will refuse to merge if the top level suite names
                    # don't match, so we need to set them all to the same name before merging them.
                    if len(outputs) > 1:
                        merged_suite_name = cast(str, ExecutionResult(*outputs).suite.name)  # pyright:ignore[reportUnknownMemberType]
                        for output in outputs:
                            _ = cast(
                                int,
                                rebot.main(
                                    [output], output=output, name=merged_suite_name, stdout=None
                                ),
                            )
                    rebot_options = merge_robot_options(
                        {
                            # rebot doesn't recreate the output.xml unless you sepecify it
                            # explicitly. we want to do this because our usage of rebot is an
                            # implementation detail and we want the output to appear the same
                            # regardless of whether the user is running with xdist
                            "output": "output.xml"
                        },
                        {
                            # filter out any robot args that aren't valid rebot args
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
                    )

                    # we need to always set the loglevel to TRACE, despite whatever it was set to
                    # when running robot. otherwise if the loglevel was changed to DEBUG or TRACE
                    # programmatically inside a test, they would not appear in the merged output
                    log_level_value = robot_args["loglevel"]
                    default_log_level = (
                        log_level_value.split(":")[1] if ":" in log_level_value else "INFO"
                    )
                    rebot_options["loglevel"] = f"TRACE:{default_log_level}"

                    _ = rebot.main(  # pyright:ignore[reportUnknownVariableType]
                        outputs,
                        # merge is deliberately specified here instead of in the merged dict because
                        # it should never be overwritten
                        merge=True,
                        **rebot_options,
                    )
            else:
                # this means robot was never run in any of the workers because there was no items,
                # so we run it here to generate an empty log file to be consistent with what would
                # happen when running with no items without xdist
                _robot_run_tests(session)
        yield
    finally:
        cringe_globals._current_session = None  # pyright:ignore[reportPrivateUsage]


def pytest_assertion_pass(item: Item, expl: str):
    """getting the explanation from this hook to pass on to the `pytest_robot_assertion` hook"""
    item.stash[_explanation_key] = expl


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


def pytest_collection(session: Session):
    _robot_collect(session)


def pytest_collect_file(parent: Collector, file_path: Path) -> Collector | None:
    if file_path.suffix == ".robot":
        return cast(
            Collector,
            RobotFile.from_parent(  # pyright:ignore[reportUnknownMemberType]
                parent, path=file_path
            ),
        )
    return None


@hookimpl(wrapper=True)
def pytest_runtest_setup(item: Item) -> HookWrapperResult:
    should_fail = item.session.shouldfail
    if should_fail:
        # this is usually handled in `pytest_runtestloop`, but since we replace it we need to
        # re-implement it here. ideally it would just stop the execution entirely instead of
        # skipping to match what pytest does by default, but we still want to generate a robot log
        skip(
            "shouldfail was set to `True`, skipping the rest of the tests"
            if isinstance(should_fail, bool)
            else should_fail
        )
    if not isinstance(item, RobotItem):
        # `set_variables` and `import_resource` is only supported in python files.
        # when running robot files, suite variables should be set using the `*** Variables ***`
        # section and resources should be imported with `Resource` in the `*** Settings***` section
        builtin = BuiltIn()
        for key, value in _suite_variables[item.path].items():
            builtin.set_suite_variable(
                r"${" + key + "}", escape_robot_str(value) if isinstance(value, str) else value
            )
        del _suite_variables[item.path]
        for resource in _resources:
            import_resource(resource)
    try:
        yield
    except BaseException as exception:
        item.stash[exception_key] = exception
        raise


@hookimpl(wrapper=True)
def pytest_runtest_call(item: Item) -> HookWrapperResult:
    try:
        yield
    except BaseException as exception:
        item.stash[exception_key] = exception
        raise


@hookimpl(wrapper=True)
def pytest_runtest_teardown(item: Item) -> HookWrapperResult:
    try:
        yield
    except BaseException as exception:
        item.stash[exception_key] = exception
        raise


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
    if session.config.option.collectonly or is_xdist(session):  # pyright:ignore[reportAny]
        # if we're running with xdist, we can't replace the runtestloop with our own because it
        # conflicts with xdist's one. instead we need to run robot individually on each test (in
        # pytest_runtest_protocol) since we can't know which tests we need to run ahead of time (i
        # think they can dynamically change mid session).
        # however if this is the xdist master and there are no items, that means none of the workers
        # are going to run robot, in which case we need to run it here to generate an empty log cuz
        # that's how robot normally behaves
        return None
    _robot_run_tests(session)
    return True


@hookimpl(tryfirst=True)
def pytest_runtest_protocol(item: Item):
    if is_xdist_worker(item.session):
        _robot_run_tests(item.session, xdist_item=item)
        return True
    return None


@hookimpl(tryfirst=True)
def pytest_terminal_summary(terminalreporter: TerminalReporter, config: Config):
    if config.option.collectonly:  # pyright:ignore[reportAny]
        return
    args = config.stash.get(_robot_args_key, None)
    if not args or not args["log"]:
        return
    log_file = Path(args["outputdir"], args["log"]).absolute()
    terminalreporter.line("")
    terminalreporter.line("Robot Framework Log File:", bold=True)
    terminalreporter.line(f"Log:     {log_file}")
    terminalreporter.line(f"Log URI: {log_file.as_uri()}")


@patch_method(ErrorDetails)
def _is_robot_traceback(  # pyright: ignore[reportUnusedFunction]
    _old_method: object, _self: ErrorDetails, tb: TracebackType
) -> bool | str | None:
    return is_robot_traceback(tb)
