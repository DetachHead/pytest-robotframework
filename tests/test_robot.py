from pytest import Pytester

from tests.utils import (
    assert_log_file_exists,
    output_xml,
    run_and_assert_result,
    run_pytest,
)


def make_robot_file(pytester: Pytester, content: str):
    pytester.makefile(".robot", content)


def test_one_test_passes(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** test cases ***
        foo
            log  1
        """,
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)


def test_one_test_fails(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** test cases ***
        foo
            fail
        """,
    )
    run_and_assert_result(pytester, failed=1)
    assert_log_file_exists(pytester)


def test_tags(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** test cases ***
        foo
            [tags]  m1
            no operation
        bar
            [tags]  m2
            no operation
        """,
    )
    run_and_assert_result(pytester, pytest_args=["-m", "m1"], passed=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(".//test[@name='foo']/tag[.='m1']")
    assert not xml.xpath(".//test[@name='bar']")


def test_doesnt_run_when_collecting(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** test cases ***
        foo
            asdfadsf
        """,
    )
    result = run_pytest(pytester, "--collect-only")
    result.assert_outcomes()
    assert not (pytester.path / "log.html").exists()
