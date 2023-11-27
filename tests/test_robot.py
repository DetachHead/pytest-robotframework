from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pytest import ExitCode, Item

from tests.utils import (
    PytesterDir,
    assert_log_file_exists,
    assert_robot_total_stats,
    output_xml,
    run_and_assert_result,
)

if TYPE_CHECKING:
    from pytest import Mark, Session


def test_one_test_passes(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)


def test_one_test_fails(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, failed=1)
    assert_log_file_exists(pytester_dir)


def test_one_test_skipped(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, skipped=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        "./suite//test[@name='Foo']/kw/msg[@level='SKIP']"
    )


def test_two_tests_one_fail_one_pass(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1, failed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath("./suite//test[@name='Foo']//kw/msg[@level='INFO' and .='1']")
    assert xml.xpath("./suite//test[@name='Bar']//kw/msg[@level='FAIL' and .='2']")


def test_listener_calls_log_file(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest(
        "--robotargs", f"--listener {pytester_dir.path / 'Listener.py'}"
    )
    result.assert_outcomes(passed=1)
    assert_log_file_exists(pytester_dir)
    assert Path("hi").exists()


def test_setup_passes(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        "./suite//test[@name='Foo']/kw[@type='SETUP']/kw[@name='Bar']/kw[@name='Log']/arg[.='2']"
    )


def test_setup_fails(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, errors=1, exit_code=ExitCode.TESTS_FAILED)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        "//suite//test[@name='Foo']/kw[@type='SETUP']/kw[@name='Bar' and"
        " .//msg[@level='FAIL' and .='asdf'] and .//status[@status='FAIL']]"
    )
    # make sure the test didnt run when setup failed
    assert not xml.xpath("//kw[contains(@name, 'Run Test')]")


def test_setup_skipped(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, skipped=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        "//suite//test[@name='Foo']/kw[@type='SETUP']/kw[@name='Bar' and"
        " .//msg[@level='SKIP']]"
    )
    # make sure the test didnt run when setup was skipped
    assert not xml.xpath("//kw[contains(@name, 'Run Test')]")


def test_teardown_passes(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        "./suite//test[@name='Foo']/kw[@type='TEARDOWN']/kw[@name='Bar']/kw[@name='Log']/arg[.='2']"
    )


def test_teardown_fails(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest()
    result.assert_outcomes(passed=1, errors=1)
    # unlike pytest, teardown failures in robot count as a test failure
    assert_robot_total_stats(pytester_dir, failed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        "//suite//test[@name='Foo']/kw[@type='TEARDOWN']/kw[@name='Bar' and"
        " .//msg[@level='FAIL' and .='asdf'] and .//status[@status='FAIL']]"
    )
    assert xml.xpath("//kw[contains(@name, 'Run Test')]")


def test_teardown_skipped(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest()
    result.assert_outcomes(passed=1, skipped=1)
    # unlike pytest, teardown skips in robot count as a test skip
    assert_robot_total_stats(pytester_dir, skipped=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        "//suite//test[@name='Foo']/kw[@type='TEARDOWN']/kw[@name='Bar' and"
        " .//msg[@level='SKIP']]"
    )
    assert xml.xpath("//kw[contains(@name, 'Run Test')]")


def test_two_files_run_one_test(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, pytest_args=["foo.robot::Foo"], passed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath("./suite//test[@name='Foo']/status[@status='PASS']")
    assert xml.xpath("./suite//test[@name='Foo']/kw/status[@status='PASS']")
    assert not xml.xpath("./suite//test[@name='Bar']")
    assert not xml.xpath("./suite//test[@name='Baz']")


def test_two_files_run_test_from_second_suite(pytester_dir: PytesterDir):
    """makes sure `PytestCollector` correctly filters the tests without mutating the list of tests
    as it iterates over it"""
    run_and_assert_result(pytester_dir, pytest_args=["fdsa/bar.robot::Baz"], passed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath("./suite//test[@name='Baz']/status[@status='PASS']")
    assert xml.xpath("./suite//test[@name='Baz']/kw/status[@status='PASS']")
    assert not xml.xpath("./suite//test[@name='Foo']")
    assert not xml.xpath("./suite//test[@name='Bar']")


def test_tags(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, pytest_args=["-m", "m1"], passed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(".//test[@name='Foo']/tag[.='m1']")
    assert not xml.xpath(".//test[@name='Bar']")


def test_tags_in_settings(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, pytest_args=["-m", "m1"], passed=2)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(".//test[@name='Foo']/tag[.='m1']")
    assert xml.xpath(".//test[@name='Bar']/tag[.='m1']")


def test_warning_on_unknown_tag(pytester_dir: PytesterDir):
    # TODO: figure out why the error message is wack
    #  https://github.com/DetachHead/pytest-robotframework/issues/37
    result = pytester_dir.runpytest("--strict-markers", "-m", "m1")
    result.assert_outcomes(errors=1)


def test_parameterized_tags(pytester_dir: PytesterDir):
    markers: list[Mark] | None = None

    class TagGetter:
        @staticmethod
        def pytest_collection_finish(session: Session):
            nonlocal markers
            for item in session.items:
                markers = item.own_markers

    result = pytester_dir.runpytest(
        "--collectonly",
        "--strict-markers",
        plugins=[TagGetter()],  # type:ignore[no-any-expr]
    )
    result.assert_outcomes()
    assert markers
    assert len(markers) == 1
    assert markers[0].name == "key"
    assert markers[0].args == ("hi",)  # type:ignore[no-any-expr]


def test_doesnt_run_when_collecting(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest("--collect-only")
    result.assert_outcomes()
    assert not (pytester_dir.path / "log.html").exists()


def test_correct_items_collected_when_collect_only(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest("--collect-only", "bar.robot")
    assert result.parseoutcomes() == {"test": 1}
    assert "<RobotItem Bar>" in (line.strip() for line in result.outlines)


# TODO: this test doesnt actually test anything
# https://github.com/DetachHead/pytest-robotframework/issues/61
def test_collect_only_nested_suites(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest("--collect-only")
    assert result.parseoutcomes() == {"tests": 2}
    assert "<RobotItem Bar>" in (line.strip() for line in result.outlines)


def test_doesnt_run_tests_outside_path(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, pytest_args=["foo"], passed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(".//test[@name='Foo']")
    assert not xml.xpath(".//test[@name='Bar']")


def test_run_keyword_and_ignore_error(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)


def test_init_file(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest()
    result.assert_outcomes(passed=1)
    assert (pytester_dir.path / "log.html").exists()
    assert output_xml(pytester_dir).xpath("/robot/suite[@name='Test Init File0']")


def test_init_file_nested(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest("foo")
    result.assert_outcomes(passed=2)
    assert (pytester_dir.path / "log.html").exists()


def test_setup_with_args(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest()
    result.assert_outcomes(passed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        "//kw[@type='SETUP']/kw[@name='Run Keywords' and ./arg[.='Bar'] and"
        " ./arg[.='AND'] and ./arg[.='Baz']]"
    )


def test_keyword_with_conflicting_name(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        "//kw[@name='Run Test']/kw[@name='Teardown' and"
        " not(@type)]/kw[@name='Log']/msg[.='1']"
    )
    assert xml.xpath(
        "//kw[@type='TEARDOWN']/kw[@name='Actual Teardown']/kw[@name='Log']/msg[.='2']"
    )


def test_no_tests_found_when_tests_exist(pytester_dir: PytesterDir):
    run_and_assert_result(
        pytester_dir, pytest_args=["asdfdsf"], exit_code=ExitCode.INTERNAL_ERROR
    )
    assert_log_file_exists(pytester_dir)


def test_keyword_decorator(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    # make sure it doesn't get double keyworded
    assert output_xml(pytester_dir).xpath(
        "//kw[@name='Run Test']/kw[@name='Bar']/msg[.='1']"
    )


def test_keyword_decorator_and_other_decorator(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    # make sure it doesn't get double keyworded
    assert output_xml(pytester_dir).xpath(
        "//kw[@name='Run Test']/kw[@name='Bar']/msg[.='1']"
    )


def test_line_number(pytester_dir: PytesterDir):
    items: list[Item] | None = None

    class ItemGetter:
        @staticmethod
        def pytest_collection_finish(session: Session):
            nonlocal items
            items = session.items

    pytester_dir.runpytest(
        "--collectonly",
        "--strict-markers",
        plugins=[ItemGetter()],  # type:ignore[no-any-expr]
    )
    assert items
    assert items[0].reportinfo()[1] == 1
    assert items[1].reportinfo()[1] == 4


def test_tags_with_kwargs(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
