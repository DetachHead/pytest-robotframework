from __future__ import annotations

from typing import Generic, Union, cast

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
    from robot.running import EXECUTION_CONTEXTS

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


class _LateFailures:
    """a failure or error that we want to re-raise at the end of the test"""

    def __init__(self):
        self.errors: list[str] = []
        self.failures: list[str] = []


robot_late_failures_key = StashKey[_LateFailures]()


def setup_late_failures(item: Item):
    if robot_late_failures_key not in item.stash:
        item.stash[robot_late_failures_key] = _LateFailures()
