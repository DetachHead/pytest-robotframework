from pytest import Pytester

from tests.utils import assert_log_file_exists, run_and_assert_result


def test_one_test_passes(pytester: Pytester):
    pytester.makefile(
        ".robot",
        """
        *** test cases ***
        foo
            log  1
        """,
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)
