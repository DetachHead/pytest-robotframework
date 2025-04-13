from __future__ import annotations

from collections.abc import Mapping
from functools import reduce
from typing import (
    TYPE_CHECKING,
    Callable,
    Final,
    Generic,
    Literal,
    Optional,
    TypedDict,
    Union,
    cast,
    final,
)

from basedtyping import T
from pytest import Item, Session, StashKey
from robot import model, running
from robot.api.interfaces import ListenerV2, ListenerV3, Parser
from robot.conf.settings import RobotSettings, _BaseSettings  # pyright:ignore[reportPrivateUsage]
from robot.running.context import _ExecutionContext  # pyright:ignore[reportPrivateUsage]
from robot.version import VERSION
from typing_extensions import override

from pytest_robotframework._internal.utils import main_package_name

if TYPE_CHECKING:
    from types import TracebackType

ModelTestCase = model.TestCase[model.Keyword]
"""robot `model.TestSuite` with the default generic value"""


ModelTestSuite = model.TestSuite[model.Keyword, ModelTestCase]
"""robot `model.TestSuite` with the default generic values"""

Listener = Union[ListenerV2, ListenerV3]


def get_arg_with_type(
    cls: type[T], args: tuple[object, ...], kwargs: Mapping[str, object]
) -> T | None:
    """
    since we rice `StatusReporter._get_failure` but it has a different signature on different
    robot versions, we need to figure out what argument it is
    """
    try:
        return next(arg for arg in (*args, *kwargs) if isinstance(arg, cls))
    except StopIteration:
        return None


class RobotOptions(TypedDict):
    """
    robot command-line arguments after being parsed by robot into a `dict`.

    for example, the following robot options:

    ```dotenv
    ROBOT_OPTIONS="--listener Foo --listener Bar -d baz"
    ```

    will be converted to a `dict` like so:
    >>> {"listener": ["Foo", "Bar"], "outputdir": "baz"}

    any options missing from this `TypedDict` are not allowed to be modified as they interfere with
    the functionality of this plugin. see https://github.com/detachhead/pytest-robotframework#config
    for alternatives
    """

    rpa: bool | None
    language: str | None
    extension: str
    name: str | None
    doc: str | None
    metadata: list[str]
    settag: list[str]
    rerunfailedsuites: list[str] | None
    skiponfailure: list[str]
    variable: list[str]
    variablefile: list[str]
    outputdir: str
    output: str | None
    log: str | None
    report: str | None
    xunit: str | None
    debugfile: str | None
    timestampoutputs: bool
    splitlog: bool
    logtitle: str | None
    reporttitle: str | None
    reportbackground: tuple[str, str] | tuple[str, str, str]
    maxerrorlines: int | None
    maxassignlength: int
    loglevel: str
    suitestatlevel: int
    tagstatinclude: list[str]
    tagstatexclude: list[str]
    tagstatcombine: list[str]
    tagdoc: list[str]
    tagstatlink: list[str]
    expandkeywords: list[str]
    removekeywords: list[str]
    flattenkeywords: list[str]
    listener: list[str | Listener]
    statusrc: bool
    skipteardownonexit: bool
    prerunmodifier: list[str | model.SuiteVisitor]
    prerebotmodifier: list[str | model.SuiteVisitor]
    randomize: Literal["ALL", "SUITES", "TESTS", "NONE"]
    console: Literal["verbose", "dotted", "quiet", "none"]
    """the default in robot is `"verbose", however pytest-robotframework changes the default to
    `"quiet"`, if you change this, then pytest and robot outputs will overlap."""
    dotted: bool
    quiet: bool
    consolewidth: int
    consolecolors: Literal["AUTO", "ON", "ANSI", "OFF"]
    consolelinks: Literal["AUTO", "OFF"]
    """only available in robotframework >=7.1.
    
    currently does nothing. see https://github.com/DetachHead/pytest-robotframework/issues/305"""
    consolemarkers: Literal["AUTO", "ON", "OFF"]
    pythonpath: list[str]
    # argumentfile is not supported because it's not in the _cli_opts dict for some reason
    # argumentfile: str | None  # noqa: ERA001
    parser: list[str | Parser]
    legacyoutput: bool
    parseinclude: list[str]
    stdout: object  # no idea what this is, it's not in the robot docs
    stderr: object  # no idea what this is, it's not in the robot docs
    exitonerror: bool


InternalRobotOptions = Mapping[str, object]
"""a less strict representation of the `RobotOptions` type. only to be used internally when working
with an incomplete robot options dict, or when using options that the user is not allowed to specify
"""

banned_options = {
    "include",
    "exclude",
    "skip",
    "test",
    "task",
    "dryrun",
    "exitonfailure",
    "rerunfailed",
    "suite",
    "runemptysuite",
    "help",
}
"""robot arguments that are not allowed because they conflict with pytest and/or this plugin"""


@final
class Cloaked(Generic[T]):
    """allows you to pass arguments to robot keywords without them appearing in the log"""

    def __init__(self, value: T):
        self.value = value

    @override
    def __str__(self) -> str:
        return ""


def execution_context() -> _ExecutionContext | None:
    # need to import it every time because it changes
    from robot.running import EXECUTION_CONTEXTS  # noqa: PLC0415

    return cast(Union[_ExecutionContext, None], EXECUTION_CONTEXTS.current)


running_test_case_key = StashKey[running.TestCase]()


def get_item_from_robot_test(
    session: Session, test: running.TestCase, *, all_items_should_have_tests: bool = True
) -> Item | None:
    """
    set `all_items_should_have_tests` to `False` if the assigning of the `running_test_case_key`
    stashes is still in progress
    """
    for item in session.items:
        found_test = (
            item.stash[running_test_case_key]
            if all_items_should_have_tests
            else item.stash.get(running_test_case_key, None)
        )
        if found_test == test:
            return item
    # the robot test was found but got filtered out by pytest, or if
    # all_items_should_have_tests=False then it was in a different worker
    return None


def full_test_name(test: ModelTestCase) -> str:
    # we cut out the top level suite name because it seems to change dynamically as more suites get
    # collected, or something
    return test.name if robot_6 else test.full_name.split(".", 1)[1]


robot_errors_key = StashKey[list[str]]()


def add_robot_error(item_or_session: Item | Session, message: str):
    if robot_errors_key not in item_or_session.stash:
        item_or_session.stash[robot_errors_key] = []
    errors = item_or_session.stash[robot_errors_key]
    errors.append(message)


def report_robot_errors(item_or_session: Item | Session) -> str | None:
    errors = item_or_session.stash.get(robot_errors_key, None)
    if not errors:
        return None
    result = "robot errors occurred and were caught by pytest-robotframework:\n\n- " + "\n- ".join(
        errors
    )
    del item_or_session.stash[robot_errors_key]
    return result


def escape_robot_str(value: str) -> str:
    r"""
    in the robot language, backslashes (`\`) get stripped as they are used as escape characters,
    so they need to be duplicated when used in keywords called from python code
    """
    return value.replace("\\", "\\\\")


def _merge_robot_options(
    dict1: InternalRobotOptions, dict2: InternalRobotOptions
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in dict1.items():
        if isinstance(value, list):
            other_value = cast(Optional[list[object]], dict2.get(key, []))
            new_value = cast(
                Optional[list[object]],
                other_value if other_value is None else [*value, *other_value],
            )
        elif key in dict2:
            new_value = dict2[key]
        else:
            new_value = value
        result[key] = new_value
    result.update({key: value for key, value in dict2.items() if key not in dict1})
    return result


def merge_robot_options(*robot_options: InternalRobotOptions) -> dict[str, object]:
    """
    merges two dicts of robot options, combining lists, or overriding them with `None` if a later
    object explicitly sets the value to `None`
    """
    return reduce(_merge_robot_options, robot_options, {})


def cli_defaults(settings_class: Callable[[dict[str, object]], _BaseSettings]) -> RobotOptions:
    # need to reset outputdir because if anything from robot gets imported before pytest runs, then
    # the cwd gets updated, robot will still run with the outdated cwd.
    # we set it in this wacky way to make sure it never overrides user preferences
    _BaseSettings._cli_opts["OutputDir"] = ("outputdir", ".")  # pyright:ignore[reportUnknownMemberType,reportPrivateUsage]
    # Need to set this so that there aren't two competing frameworks dumping into the console
    RobotSettings._extra_cli_opts["ConsoleType"] = ("console", "quiet")  # pyright:ignore[reportUnknownMemberType,reportPrivateUsage]
    # https://github.com/DetachHead/basedpyright#note-about-casting-with-typeddicts
    return cast(  # pyright:ignore[reportInvalidCast]
        RobotOptions,
        dict(
            # instantiate the class because _BaseSettings.__init__ adds any additional opts
            # that the subclass may have defined (using _extra_cli_opts)
            settings_class(  # pyright:ignore[reportUnknownArgumentType,reportUnknownMemberType]
                {}
            )._cli_opts.values()  # pyright:ignore[reportPrivateUsage]
        ),
    )


robot_6: Final = VERSION.startswith("6.")


def is_robot_traceback(tb: TracebackType) -> bool | str | None:
    """Consider all the extended framework as 'robot'"""
    # importing these modules here because i don't want whole module imports to be available at the
    # top level
    import _pytest  # noqa: PLC0415
    import pluggy  # noqa: PLC0415
    import pytest  # noqa: PLC0415
    import robot  # noqa: PLC0415

    module_name = cast(
        Optional[str], cast(dict[str, object], tb.tb_frame.f_globals).get("__name__")
    )
    # not importing pytest_robotframework itself because it would cause circular imports
    return module_name == main_package_name or (
        module_name
        and module_name.startswith((
            *(f"{module.__name__}." for module in (robot, pytest, _pytest, pluggy)),
            main_package_name,
        ))
    )
