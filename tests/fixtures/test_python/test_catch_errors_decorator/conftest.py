from __future__ import annotations

from typing import TYPE_CHECKING

from robot.api.interfaces import ListenerV3
from typing_extensions import override

from pytest_robotframework import listener

if TYPE_CHECKING:
    from robot import model, result


@listener
class Listener(ListenerV3):
    @override
    def end_test(self, data: model.TestCase, result: result.TestCase):
        raise Exception("asdf")
