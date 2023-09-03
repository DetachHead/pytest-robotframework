from __future__ import annotations

from pytest import ExitCode, Pytester

from tests.utils import assert_log_file_exists, run_and_assert_result


def test_no_tests_found_no_files(pytester: Pytester):
    run_and_assert_result(pytester, exit_code=ExitCode.NO_TESTS_COLLECTED)
    assert_log_file_exists(pytester)
