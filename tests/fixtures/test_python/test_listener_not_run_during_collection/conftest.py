from __future__ import annotations

from typing import TYPE_CHECKING

from robot.api.interfaces import ListenerV3
from typing_extensions import override

if TYPE_CHECKING:
    from robot import result, running

    from pytest_robotframework import RobotOptions

called = False


class Listener(ListenerV3):
    @override
    def start_suite(self, data: running.TestSuite, result: result.TestSuite):
        global called
        called = True


def pytest_robot_modify_options(options: RobotOptions):
    options["listener"].append(Listener())


def pytest_sessionfinish():
    assert not called
