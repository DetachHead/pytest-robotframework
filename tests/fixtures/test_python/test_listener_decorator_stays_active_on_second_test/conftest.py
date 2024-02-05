# noqa: INP001
# init file breaks it
from __future__ import annotations

from typing import TYPE_CHECKING

from robot.api.interfaces import ListenerV3
from typing_extensions import override

from pytest_robotframework import listener

if TYPE_CHECKING:
    from robot import result, running

ran = False


@listener
class Listener(ListenerV3):
    @override
    def start_test(self, data: running.TestCase, result: result.TestCase):
        global ran
        ran = True

    @override
    def end_test(self, data: running.TestCase, result: result.TestCase):
        global ran
        ran = False
