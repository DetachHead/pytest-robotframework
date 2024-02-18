# noqa: N999
# module needs to have the same name as the class when registering the listener with the cli
from __future__ import annotations

from typing import TYPE_CHECKING

from robot.api.interfaces import ListenerV3
from typing_extensions import override

if TYPE_CHECKING:
    from robot import result, running

called = False


class Listener(ListenerV3):
    @override
    def start_suite(self, data: running.TestSuite, result: result.TestSuite):
        global called
        called = True
