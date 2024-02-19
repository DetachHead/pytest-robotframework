from __future__ import annotations

import inspect
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Callable, cast

from basedtyping import Function
from robot.running.librarykeywordrunner import LibraryKeywordRunner
from robot.running.statusreporter import StatusReporter
from robot.utils.error import ErrorDetails
from typing_extensions import override

from pytest_robotframework._internal.errors import InternalError
from pytest_robotframework._internal.robot_utils import is_robot_traceback, robot_6
from pytest_robotframework._internal.utils import main_package_name, patch_method

if TYPE_CHECKING:
    from robot.running.context import _ExecutionContext  # pyright:ignore[reportPrivateUsage]

kw_attribute = "_keyword_original_function"

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
        handler = cast(Function, getattr(handler, kw_attribute, handler))
        return old_method(self, context, handler, positional, named)

else:
    from robot.running.librarykeyword import StaticKeyword, StaticKeywordCreator

    class _StaticKeyword(StaticKeyword):  # pylint:disable=abstract-method
        """prevents keywords decorated with `pytest_robotframework.keyword` from being wrapped in
        two status reporters when called from `.robot` tests"""

        @property
        @override
        def method(self) -> Function:
            method = cast(Function, super().method)
            return cast(Function, getattr(method, kw_attribute, method))

        @override
        def copy(self, **attributes: object) -> _StaticKeyword:
            return _StaticKeyword(  # pyright:ignore[reportUnknownMemberType]
                self.method_name,
                self.owner,
                self.name,
                self.args,
                self._doc,
                self.tags,
                self._resolve_args_until,
                self.parent,
                self.error,
            ).config(**attributes)

    # patch StaticKeywordCreator to use our one instead
    StaticKeywordCreator.keyword_class = (  # pyright:ignore[reportGeneralTypeIssues]
        _StaticKeyword
    )


@patch_method(ErrorDetails)
def _is_robot_traceback(  # pyright: ignore[reportUnusedFunction]
    _old_method: object, _self: ErrorDetails, tb: TracebackType
) -> bool | str | None:
    return is_robot_traceback(tb)


class FullStackStatusReporter(StatusReporter):
    """Riced status reporter that inserts the full test traceback"""

    @override
    def _get_failure(
        self,
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType,
        context: object,
    ):
        full_system_traceback = inspect.stack()
        tb = None

        in_framework = True
        base_tb = exc_tb
        while base_tb and is_robot_traceback(base_tb):
            base_tb = base_tb.tb_next
        for frame in full_system_traceback:
            trace = TracebackType(
                tb or base_tb, frame.frame, frame.frame.f_lasti, frame.frame.f_lineno
            )
            if in_framework and is_robot_traceback(trace):
                continue
            in_framework = False
            tb = trace
            if str(Path(frame.filename)).endswith(
                str(Path(main_package_name) / "_internal/plugin.py")
            ):
                break
        else:
            raise InternalError("erm...")
        exc_value.__traceback__ = tb
        return super()._get_failure(exc_value, exc_value, tb, context)  # pyright: ignore[reportUnknownMemberType]
