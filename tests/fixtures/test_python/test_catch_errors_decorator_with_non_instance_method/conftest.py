from __future__ import annotations

from typing import TYPE_CHECKING

from robot.api.interfaces import ListenerV3
from typing_extensions import override

from pytest_robotframework import listener

if TYPE_CHECKING:
    from robot import result, running


@listener
class Listener(ListenerV3):
    @staticmethod
    def static_method():
        pass

    @classmethod
    def class_method(cls):
        pass

    @override
    def start_test(self, data: running.TestCase, result: result.TestCase):
        self.static_method()
        self.class_method()
