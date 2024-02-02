from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_robotframework import RobotOptions


def pytest_robot_modify_options(options: RobotOptions):
    options["variable"] = ["foo:bar"]
