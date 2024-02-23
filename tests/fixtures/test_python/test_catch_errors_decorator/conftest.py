from __future__ import annotations

from typing import TYPE_CHECKING

from robot.api.interfaces import ListenerV3
from typing_extensions import override

from pytest_robotframework import RobotOptions, catch_errors

if TYPE_CHECKING:
    from robot import result, running


@catch_errors
class Listener(ListenerV3):
    @override
    def end_test(self, data: running.TestCase, result: result.TestCase):
        raise Exception("asdf")


def pytest_robot_modify_options(options: RobotOptions):
    options["listener"].append(Listener())
