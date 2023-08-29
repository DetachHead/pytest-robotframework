# noqa: INP001
# init file breaks it and i dont care because i hate init files
from __future__ import annotations

from typing import TYPE_CHECKING

from robot.api.interfaces import ListenerV3
from typing_extensions import override

if TYPE_CHECKING:
    from robot import result, running

called = False


class Listener(ListenerV3):
    @override
    def start_suite(
        self,
        data: running.TestSuite,
        result: result.TestSuite,  # pylint:disable=redefined-outer-name
    ):
        global called
        called = True
