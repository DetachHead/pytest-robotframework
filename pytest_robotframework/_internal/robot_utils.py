from __future__ import annotations

from typing import cast

from robot.running import EXECUTION_CONTEXTS
from robot.running.context import (  # pylint:disable=import-private-name
    _ExecutionContext,
)


def execution_context() -> _ExecutionContext | None:
    return cast(_ExecutionContext | None, EXECUTION_CONTEXTS.current)
