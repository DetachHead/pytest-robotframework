from __future__ import annotations

from typing import TYPE_CHECKING, Callable, cast

from basedtyping import Function
from robot.running.librarykeywordrunner import LibraryKeywordRunner
from robot.utils.error import ErrorDetails

from pytest_robotframework import (
    _keyword_original_function_attr,  # pyright:ignore[reportPrivateUsage]
)
from pytest_robotframework._internal.robot_utils import is_robot_traceback, robot_6
from pytest_robotframework._internal.utils import patch_method

if TYPE_CHECKING:
    from types import TracebackType

    from robot.running.context import _ExecutionContext  # pyright:ignore[reportPrivateUsage]


# in robot 7 this is done by the KeywordUnwrapper listener
if robot_6:

    @patch_method(LibraryKeywordRunner)
    def _runner_for(  # pyright:ignore[reportUnusedFunction] # noqa: PLR0917
        old_method: Callable[
            [LibraryKeywordRunner, _ExecutionContext, Function, list[object], dict[str, object]],
            Function,
        ],
        self: LibraryKeywordRunner,
        context: _ExecutionContext,
        handler: Function,
        positional: list[object],
        named: dict[str, object],
    ) -> Function:
        """use the original function instead of the `@keyword` wrapped one"""
        handler = cast(Function, getattr(handler, _keyword_original_function_attr, handler))
        return old_method(self, context, handler, positional, named)


@patch_method(ErrorDetails)
def _is_robot_traceback(  # pyright: ignore[reportUnusedFunction]
    _old_method: object, _self: ErrorDetails, tb: TracebackType
) -> bool | str | None:
    return is_robot_traceback(tb)
