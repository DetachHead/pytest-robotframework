# noqa: INP001
# init file breaks it
from __future__ import annotations

from typing import TYPE_CHECKING

from robot.api.interfaces import ListenerV3
from typing_extensions import override

from pytest_robotframework import listener  # pyright:ignore[reportDeprecated]

if TYPE_CHECKING:
    from robot import result, running

ran = False


@listener  # pyright:ignore[reportDeprecated]
class Listener(ListenerV3):
    @override
    def start_test(self, data: running.TestCase, result: result.TestCase):
        global ran
        ran = True
