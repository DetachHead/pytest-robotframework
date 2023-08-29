from __future__ import annotations

from typing import TYPE_CHECKING

from tests.utils import assert_log_file_exists, run_and_assert_result

if TYPE_CHECKING:
    from pytest import Pytester


def test_no_tests_found_no_files(pytester: Pytester):
    run_and_assert_result(pytester)
    assert_log_file_exists(pytester)
