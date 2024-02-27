from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Final,
    Generic,
    List,
    Literal,
    Mapping,
    Optional,
    TypedDict,
    Union,
    cast,
)

from basedtyping import T
from pytest import Item, Session, StashKey
from robot import model, running
from robot.api.interfaces import ListenerV2, ListenerV3, Parser
from robot.conf.settings import _BaseSettings  # pyright:ignore[reportPrivateUsage]
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


class RobotOptions(TypedDict):
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
    dotted: bool
    quiet: bool
    consolewidth: int
    consolecolors: Literal["AUTO", "ON", "ANSI", "OFF"]
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


class Cloaked(Generic[T]):
    """allows you to pass arguments to robot keywords without them appearing in the log"""

    def __init__(self, value: T):
        super().__init__()
        self.value = value

    @override
    def __str__(self) -> str:
        return ""


def execution_context() -> _ExecutionContext | None:
    # need to import it every time because it changes
    from robot.running import EXECUTION_CONTEXTS  # noqa: PLC0415

    return cast(
        Union[_ExecutionContext, None],
        EXECUTION_CONTEXTS.current,  # pyright:ignore[reportUnknownMemberType]
    )


running_test_case_key = StashKey[running.TestCase]()


def get_item_from_robot_test(
    session: Session, test: running.TestCase, *, all_items_should_have_tests: bool = True
) -> Item | None:
    """set `all_items_should_have_tests` to `False` if the assigning of the `running_test_case_key`
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
    return test.name if robot_6 else test.full_name


robot_errors_key = StashKey[List[str]]()


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
    r"""in the robot language, backslashes (`\`) get stripped as they are used as escape characters,
    so they need to be duplicated when used in keywords called from python code"""
    return value.replace("\\", "\\\\")


# not using RobotOptions type since we use it to set banned options that we don't expose to the user
def merge_robot_options(
    obj1: Mapping[str, object], obj2: Mapping[str, object]
) -> dict[str, object]:
    """this assumes there are no nested dicts (as far as i can tell no robot args be like that)"""
    result: dict[str, object] = {}
    for key, value in obj1.items():
        if isinstance(value, list):
            other_value = cast(Optional[List[object]], obj2.get(key, []))
            new_value = cast(List[object], value if other_value is None else [*value, *other_value])
        elif key in obj2:
            new_value = obj2[key]
        else:
            new_value = value
        result[key] = new_value
    result.update({key: value for key, value in obj2.items() if key not in obj1})
    return result


def cli_defaults(settings_class: Callable[[dict[str, object]], _BaseSettings]) -> RobotOptions:
    # need to reset outputdir because if anything from robot gets imported before pytest runs, then
    # the cwd gets updated, robot will still run with the outdated cwd.
    # we set it in this wacky way to make sure it never overrides user preferences
    _BaseSettings._cli_opts["OutputDir"] = ("outputdir", ".")  # pyright:ignore[reportUnknownMemberType,reportPrivateUsage]

    return cast(
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
        Optional[str], cast(Dict[str, object], tb.tb_frame.f_globals).get("__name__")
    )
    # not importing pytest_robotframework itself because it would cause circular imports
    return module_name == main_package_name or (
        module_name
        and module_name.startswith((
            *(f"{module.__name__}." for module in (robot, pytest, _pytest, pluggy)),
            main_package_name,
        ))
    )
