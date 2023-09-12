from __future__ import annotations

from typing import Generic, Union, cast

from basedtyping import T
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
