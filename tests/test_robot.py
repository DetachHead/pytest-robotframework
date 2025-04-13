from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, cast

from pytest import ExitCode, Item, Mark

from pytest_robotframework._internal.robot.utils import robot_6
from tests.conftest import PytestRobotTester, assert_robot_total_stats, output_xml, xpath

if TYPE_CHECKING:
    from pytest import Session


def test_one_test_passes(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_one_test_fails(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()


def test_one_test_skipped(pr: PytestRobotTester):
    pr.run_and_assert_result(skipped=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath("./suite//test[@name='Foo']/kw/msg[@level='SKIP']")


def test_two_tests_one_fail_one_pass(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1, failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath("./suite//test[@name='Foo']//kw/msg[@level='INFO' and .='1']")
    assert xml.xpath("./suite//test[@name='Bar']//kw/msg[@level='FAIL' and .='2']")


def test_listener_calls_log_file(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result(
        "--robot-listener", str(pr.pytester.path / "Listener.py"), passed=1
    )
    pr.assert_log_file_exists()
    # the log file does not get created by robot when running in xdist mode, instead it gets created
    # later by rebot, so the listener method is never called
    assert pr.xdist != Path("hi").exists()


def test_setup_passes(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath(
        "./suite//test[@name='Foo']/kw[@type='SETUP']/kw[@name='Bar']/kw[@name='Log']/arg[.='2']"
    )


def test_setup_fails(pr: PytestRobotTester):
    pr.run_and_assert_result(errors=1, exit_code=ExitCode.TESTS_FAILED)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//suite//test[@name='Foo']/kw[@type='SETUP']/kw[@name='Bar' and"
        " .//msg[@level='FAIL' and .='asdf'] and .//status[@status='FAIL']]"
    )
    # make sure the test didnt run when setup failed
    assert not xml.xpath("//kw[contains(@name, 'Run Test')]")


def test_setup_skipped(pr: PytestRobotTester):
    pr.run_and_assert_result(skipped=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//suite//test[@name='Foo']/kw[@type='SETUP']/kw[@name='Bar' and .//msg[@level='SKIP']]"
    )
    # make sure the test didnt run when setup was skipped
    assert not xml.xpath("//kw[contains(@name, 'Run Test')]")


def test_teardown_passes(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath(
        "./suite//test[@name='Foo']/kw[@type='TEARDOWN']/kw[@name='Bar']/kw[@name='Log']/arg[.='2']"
    )


def test_teardown_fails(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result(passed=1, errors=1, exit_code=ExitCode.TESTS_FAILED)
    # unlike pytest, teardown failures in robot count as a test failure
    assert_robot_total_stats(failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//suite//test[@name='Foo']/kw[@type='TEARDOWN']/kw[@name='Bar' and"
        " .//msg[@level='FAIL' and .='asdf'] and .//status[@status='FAIL']]"
    )
    assert xml.xpath("//kw[contains(@name, 'Run Test')]")


def test_teardown_skipped(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result(passed=1, skipped=1)
    # unlike pytest, teardown skips in robot count as a test skip
    assert_robot_total_stats(skipped=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//suite//test[@name='Foo']/kw[@type='TEARDOWN']/kw[@name='Bar' and .//msg[@level='SKIP']]"
    )
    assert xml.xpath("//kw[contains(@name, 'Run Test')]")


def test_two_files_run_one_test(pr: PytestRobotTester):
    pr.run_and_assert_result("foo.robot::Foo", passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath("./suite//test[@name='Foo']/status[@status='PASS']")
    assert xml.xpath("./suite//test[@name='Foo']/kw/status[@status='PASS']")
    assert not xml.xpath("./suite//test[@name='Bar']")
    assert not xml.xpath("./suite//test[@name='Baz']")


def test_two_files_run_test_from_second_suite(pr: PytestRobotTester):
    """
    makes sure `PytestCollector` correctly filters the tests without mutating the list of tests
    as it iterates over it
    """
    pr.run_and_assert_result("fdsa/bar.robot::Baz", passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath("./suite//test[@name='Baz']/status[@status='PASS']")
    assert xml.xpath("./suite//test[@name='Baz']/kw/status[@status='PASS']")
    assert not xml.xpath("./suite//test[@name='Foo']")
    assert not xml.xpath("./suite//test[@name='Bar']")


def test_run_two_files(pr: PytestRobotTester):
    pr.run_and_assert_result("a.robot", "b.robot", passed=2)
    pr.assert_log_file_exists()


def test_tags(pr: PytestRobotTester):
    pr.run_and_assert_result("-m", "m1", passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test[@name='Foo']/tag[.='m1']")
    assert not xml.xpath(".//test[@name='Bar']")


def test_tags_in_settings(pr: PytestRobotTester):
    pr.run_and_assert_result("-m", "m1", passed=2)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test[@name='Foo']/tag[.='m1']")
    assert xml.xpath(".//test[@name='Bar']/tag[.='m1']")


def test_warning_on_unknown_tag(pr: PytestRobotTester):
    result = pr.run_pytest("--strict-markers", "-m", "m1")
    result.assert_outcomes(errors=pr.xdist or 1)
    assert result.ret == ExitCode.TESTS_FAILED
    assert "'m1' not found in `markers` configuration option" in result.outlines


def test_parameterized_tags(pr: PytestRobotTester):
    # cast because it gets narrowed on assignment but widened non-locally
    # https://github.com/DetachHead/basedpyright/issues/439
    markers = cast(Optional[list[Mark]], None)

    class TagGetter:
        @staticmethod
        def pytest_collection_finish(session: Session):
            nonlocal markers
            for item in session.items:
                markers = item.own_markers

    pr.run_and_assert_assert_pytest_result(
        "--collectonly", "--strict-markers", plugins=[TagGetter()], subprocess=False
    )
    assert markers
    assert len(markers) == 1
    assert markers[0].name == "key"
    assert markers[0].args == ("hi",)


def test_doesnt_run_when_collecting(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result("--collect-only", subprocess=False)
    pr.assert_log_file_doesnt_exist()


def test_correct_items_collected_when_collect_only(pr: PytestRobotTester):
    result = pr.run_pytest("--collect-only", "bar.robot", subprocess=False)
    assert result.parseoutcomes() == {"test": 1}
    assert "<RobotItem Bar>" in (line.strip() for line in result.outlines)


# TODO: this test doesnt actually test anything
# https://github.com/DetachHead/pytest-robotframework/issues/61
def test_collect_only_nested_suites(pr: PytestRobotTester):
    result = pr.run_pytest("--collect-only", subprocess=False)
    assert result.parseoutcomes() == {"tests": 2}
    assert "<RobotItem Bar>" in (line.strip() for line in result.outlines)


def test_doesnt_run_tests_outside_path(pr: PytestRobotTester):
    pr.run_and_assert_result("foo", passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test[@name='Foo']")
    assert not xml.xpath(".//test[@name='Bar']")


def test_run_keyword_and_ignore_error(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_init_file(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert cast(str, xpath(output_xml(), "/robot/suite").attrib["name"]).startswith(
        "Test Init File"
    )


def test_init_file_nested(pr: PytestRobotTester):
    pr.run_and_assert_result("foo", passed=2)
    pr.assert_log_file_exists()


def test_setup_with_args(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//kw[@type='SETUP']/kw[@name='Run Keywords' and ./arg[.='Bar'] and"
        " ./arg[.='AND'] and ./arg[.='Baz']]"
    )


def test_keyword_with_conflicting_name(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//kw[@name='Run Test']/kw[@name='Teardown' and not(@type)]/kw[@name='Log']/msg[.='1']"
    )
    assert xml.xpath(
        "//kw[@type='TEARDOWN']/kw[@name='Actual Teardown']/kw[@name='Log']/msg[.='2']"
    )


def test_no_tests_found_when_tests_exist(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result("asdfdsf", exit_code=ExitCode.USAGE_ERROR)


def test_keyword_decorator(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    # make sure it doesn't get double keyworded
    assert output_xml().xpath("//kw[@name='Run Test']/kw[@name='Bar']/msg[.='1']")


def test_keyword_decorator_and_other_decorator(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    # make sure it doesn't get double keyworded
    assert output_xml().xpath("//kw[@name='Run Test']/kw[@name='Bar']/msg[.='1']")


def test_line_number(pr: PytestRobotTester):
    items = cast(Optional[list[Item]], None)

    class ItemGetter:
        @staticmethod
        def pytest_collection_finish(session: Session):
            nonlocal items
            items = session.items

    _ = pr.run_pytest("--collectonly", "--strict-markers", plugins=[ItemGetter()], subprocess=False)
    assert items
    assert items[0].reportinfo()[1] == 1
    assert items[1].reportinfo()[1] == 4


def test_tags_with_kwargs(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_nested_keyword_that_fails(pr: PytestRobotTester):
    pr.run_and_assert_result("-o", "enable_assertion_pass_hook=true", subprocess=True, failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xpath(xml, "//kw[@name='Bar']/kw[@name='Baz']/msg[@level='FAIL' and .='asdf']")
    # make sure the error was only logged once, since the exception gets re-raised after the
    # keyword is over we want to make sure it's not printed multiple times
    assert xpath(xml, "//msg[@level='FAIL']")


def test_fails_when_import_error_and_exit_on_error(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result("--robot-exitonerror", exit_code=ExitCode.INTERNAL_ERROR)
    assert_robot_total_stats(failed=1)


def test_traceback(pr: PytestRobotTester):
    result = pr.run_pytest("--tb=short")
    assert """
util.py:5: in thing
    raise Exception("asdf")
E   Exception: asdf
""" in "\n".join(result.outlines)


def test_empty_setup_or_teardown(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=3)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xpath(
        xml,
        "//test[@name='Runs globally defined setup and teardown']/kw[@name='Setup']/kw[@name='Log']"
        "/msg[.='setup ran']",
    )
    assert xpath(
        xml,
        "//test[@name='Runs globally defined setup and teardown']/kw[@name='Teardown']"
        "/kw[@name='Log']/msg[.='teardown ran']",
    )
    assert not xml.xpath("//test[@name='Disable setup']/kw[@name='Setup']/kw[@name='Log']")
    assert not xml.xpath("//test[@name='Disable teardown']/kw[@name='Teardown']/kw[@name='Log']")


def test_keyword_decorator_class_library(pr: PytestRobotTester):
    pr.run_and_assert_result("--robot-loglevel", "DEBUG:INFO", passed=1)
    pr.assert_log_file_exists()
    assert xpath(
        output_xml(),
        f"//kw[@name='Foo' and @{'library' if robot_6 else 'owner'}='ClassLibrary']/msg[.='hi']",
    )


def test_pass_execution(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
