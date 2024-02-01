from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import ExitCode

if TYPE_CHECKING:
    from conftest import PytestRobotTester


def test_no_tests_found_no_files(pr: PytestRobotTester):
    pr.run_and_assert_result(exit_code=ExitCode.NO_TESTS_COLLECTED)
    pr.assert_log_file_exists(check_xdist=False)
