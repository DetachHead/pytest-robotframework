from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import ExitCode, mark
from robot.conf.settings import RobotSettings

from pytest_robotframework import RobotOptions
from pytest_robotframework._internal.robot.utils import banned_options, cli_defaults, robot_6

if TYPE_CHECKING:
    from tests.conftest import PytestRobotTester


def test_no_tests_found_no_files(pr: PytestRobotTester):
    pr.run_and_assert_result(exit_code=ExitCode.NO_TESTS_COLLECTED)
    pr.assert_log_file_exists(check_xdist=False)


# i don't care to maintain multiple versions of this type so only test against the latest version
@mark.skipif(robot_6, reason="old robot version")
def test_robot_options_type_is_up_to_date():
    assert {key for key in cli_defaults(RobotSettings) if key not in banned_options} == set(
        RobotOptions.__annotations__.keys()
    )


def test_robot_file_and_python_file(pr: PytestRobotTester):
    pr.run_and_assert_result("foo.robot", "test_bar.py", passed=2)
    pr.assert_log_file_exists()
