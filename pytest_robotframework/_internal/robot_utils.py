from __future__ import annotations

from typing import Dict, Final, Generic, List, Union, cast

from basedtyping import T
from pytest import Item, Session, StashKey
from robot import model, running
from robot.running.context import (
    _ExecutionContext,  # pyright:ignore[reportPrivateUsage]
)
from robot.version import VERSION
from typing_extensions import override

ModelTestCase = model.TestCase[model.Keyword]
"""robot `model.TestSuite` with the default generic value"""


ModelTestSuite = model.TestSuite[model.Keyword, ModelTestCase]
"""robot `model.TestSuite` with the default generic values"""


RobotArgs = Dict[str, object]


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
    session: Session,
    test: running.TestCase,
    *,
    all_items_should_have_tests: bool = True,
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
    result = (
        "robot errors occurred and were caught by pytest-robotframework:\n\n- "
        + "\n- ".join(errors)
    )
    del item_or_session.stash[robot_errors_key]
    return result


def escape_robot_str(value: str) -> str:
    r"""in the robot language, backslashes (`\`) get stripped as they are used as escape characters,
    so they need to be duplicated when used in keywords called from python code"""
    return value.replace("\\", "\\\\")


def merge_robot_options(obj1: RobotArgs, obj2: RobotArgs) -> RobotArgs:
    """this assumes there are no nested dicts (as far as i can tell no robot args be like that)"""
    result: RobotArgs = {}
    for key, value in obj1.items():
        if isinstance(value, list):
            new_value = cast(
                List[object],
                [*value, *cast(Dict[str, List[object]], obj2.get(key, []))],
            )
        elif key in obj2:
            new_value = obj2[key]
        else:
            new_value = value
        result[key] = new_value
    for key, value in obj2.items():
        if key not in obj1:
            result[key] = value
    return result


robot_6: Final = VERSION.startswith("6.")
