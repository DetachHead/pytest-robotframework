from __future__ import annotations

from typing import Generic, List, Union, cast

from basedtyping import T
from pytest import Item, Session, StashKey
from robot import running
from robot.running.context import _ExecutionContext
from typing_extensions import override


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


def get_item_from_robot_test(session: Session, test: running.TestCase) -> Item | None:
    try:
        return next(
            item for item in session.items if item.stash[running_test_case_key] == test
        )
    except StopIteration:
        # the robot test was found but got filtered out by pytest
        return None


robot_errors_key = StashKey[List[str]]()


def add_robot_error(item_or_session: Item | Session, message: str):
    if robot_errors_key not in item_or_session.stash:
        # https://github.com/python/mypy/issues/230
        item_or_session.stash[robot_errors_key] = []  # type:ignore[misc]
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
