from __future__ import annotations

from typing import TYPE_CHECKING, final

from robot.api.interfaces import ListenerV3
from typing_extensions import override

if TYPE_CHECKING:
    from robot import result, running

    from pytest_robotframework import RobotOptions


@final
class Foo(ListenerV3):
    def __init__(self):
        super().__init__()
        self.ran = False

    @override
    def start_test(self, data: running.TestCase, result: result.TestCase):
        self.ran = True


foo = Foo()


def pytest_robot_modify_options(options: RobotOptions):
    options["listener"] = [foo]


def pytest_runtest_setup():
    assert foo.ran
