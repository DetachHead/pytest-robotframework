from __future__ import annotations

from abc import ABC, abstractmethod
from itertools import groupby
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


class _LateFailure(ABC):
    """a failure or error that we want to re-raise at the end of the test"""

    def __init__(self, message: str) -> None:
        self.message = message

    @staticmethod
    @abstractmethod
    def description() -> str: ...


class ContinuableFailure(_LateFailure):
    def __init__(self, error: BaseException):
        super().__init__(str(error))

    @staticmethod
    @override
    def description() -> str:
        return "failures that occurred inside a `continue_on_failure`"


class RobotError(_LateFailure):
    @staticmethod
    @override
    def description() -> str:
        return "robot errors"


robot_late_failures_key = StashKey[List[_LateFailure]]()


def add_late_failure(item_or_session: Item | Session, failure: _LateFailure):
    """adds a failure to be raised at the end of the test. `fail` is for failures that occurred
    inside `continue_on_failure`, `error` is for robot errors"""
    if robot_late_failures_key not in item_or_session.stash:
        # https://github.com/python/mypy/issues/230
        item_or_session.stash[robot_late_failures_key] = []  # type:ignore[misc]
    late_failures = item_or_session.stash[robot_late_failures_key]
    late_failures.append(failure)


def describe_late_failures(item_or_session: Item | Session) -> str | None:
    late_failures = item_or_session.stash.get(robot_late_failures_key, None)
    if late_failures:
        failure_groups = groupby(late_failures, lambda failure: failure.description())
        result = ""
        for description, failures in failure_groups:
            messages = [failure.message for failure in failures]
            if not messages:
                continue
            # need separate variable because \n doesn't work inside nested f strings
            list_str = "\n- ".join(messages)
            result += f"{description}:\n\n- {list_str}\n\n"
        del item_or_session.stash[robot_late_failures_key]
        return result
    return None


def escape_robot_str(value: str) -> str:
    r"""in the robot language, backslashes (`\`) get stripped as they are used as escape characters,
    so they need to be duplicated when used in keywords called from python code"""
    return value.replace("\\", "\\\\")
