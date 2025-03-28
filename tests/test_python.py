from __future__ import annotations

import re
import sys
from pathlib import Path
from re import search
from typing import TYPE_CHECKING, cast

from _pytest.assertion.util import running_on_ci
from pytest import ExitCode, MonkeyPatch, skip

from pytest_robotframework._internal.robot.utils import robot_6
from tests.conftest import (
    PytestRobotTester,
    XmlElement,
    assert_robot_total_stats,
    output_xml,
    xpath,
)

if TYPE_CHECKING:
    from tests.conftest import PytesterDir


def test_one_test_passes(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_one_test_fails(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()


def test_one_test_skipped(pr: PytestRobotTester):
    pr.run_and_assert_result(skipped=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath(
        "./suite//test[@name='test_one_test_skipped']/kw[@type='SETUP']/msg[@level='SKIP' and "
        ".='Skipped: foo']"
    )


def test_two_tests_one_fail_one_pass(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1, failed=1)
    pr.assert_log_file_exists()


def test_two_tests_two_files_one_fail_one_pass(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1, failed=1)
    pr.assert_log_file_exists()


def test_run_two_files(pr: PytestRobotTester):
    pr.run_and_assert_result("test_a.py", "test_b.py", passed=2)
    pr.assert_log_file_exists()


def test_two_tests_with_same_name_one_fail_one_pass(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1, failed=1)
    pr.assert_log_file_exists()


def test_suites(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath(
        "./suite/suite[@name='Suite1']/suite[@name='Test Asdf']/test[@name='test_func1']"
    )


def test_nested_suites(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=2, failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "./suite/suite[@name='Suite1']/suite[@name='Suite2']/suite[@name='Test"
        " Asdf']/test[@name='test_func1']"
    )
    assert xml.xpath(
        "./suite/suite[@name='Suite1']/suite[@name='Suite3']/suite[@name='Test"
        " Asdf2']/test[@name='test_func2']"
    )
    assert xml.xpath("./suite/suite[@name='Test Top Level']/test[@name='test_func1']")


def test_robot_options_variable(pr: PytestRobotTester, monkeypatch: MonkeyPatch):
    results_path = pr.pytester.path / "results"
    monkeypatch.setenv("ROBOT_OPTIONS", f"-d {results_path}")
    pr.run_and_assert_assert_pytest_result(passed=1, subprocess=True)
    assert (results_path / "log.html").exists()


def test_robot_options_merge_listeners(pr: PytestRobotTester):
    pr.run_and_assert_result(
        "--robot-listener", str(pr.pytester.path / "Listener.py"), subprocess=True, passed=1
    )
    pr.assert_log_file_exists()


def test_listener_not_run_during_collection(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result("--collect-only", subprocess=True)
    pr.assert_log_file_doesnt_exist()


def test_robot_options_variable_merge_listeners(pr: PytestRobotTester, monkeypatch: MonkeyPatch):
    monkeypatch.setenv("ROBOT_OPTIONS", f"--listener {pr.pytester.path / 'Listener.py'}")
    pr.run_and_assert_result(passed=1, subprocess=True)
    pr.assert_log_file_exists()


def test_robot_modify_options_hook(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_robot_modify_options_hook_listener_instance(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_listener_calls_log_file(pr: PytestRobotTester):
    pr.run_and_assert_result(
        "--robot-listener", str(pr.pytester.path / "Listener.py"), subprocess=True, passed=1
    )
    pr.assert_log_file_exists()
    # the log file does not get created by robot when running in xdist mode, instead it gets created
    # later by rebot, so the listener method is never called
    assert pr.xdist != Path("hi").exists()


def test_doesnt_run_when_collecting(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result("--collect-only", subprocess=True)
    pr.assert_log_file_doesnt_exist()


# TODO: this test doesnt actually test anything
# https://github.com/DetachHead/pytest-robotframework/issues/61
def test_collect_only_nested_suites(pr: PytestRobotTester):
    result = pr.run_pytest("--collect-only", subprocess=True)
    assert result.parseoutcomes() == {"tests": 2}
    assert "<Function test_func2>" in (line.strip() for line in result.outlines)


def test_correct_items_collected_when_collect_only(pr: PytestRobotTester):
    result = pr.run_pytest("--collect-only", "test_bar.py", subprocess=True)
    assert result.parseoutcomes() == {"test": 1}
    assert "<Function test_func2>" in (line.strip() for line in result.outlines)


def test_setup_passes(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test/kw[@name='Setup']/msg[@level='INFO' and .='2']")
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='1']")


def test_setup_fails(pr: PytestRobotTester):
    pr.run_and_assert_result(errors=1, exit_code=ExitCode.TESTS_FAILED)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test/kw[@name='Setup']/msg[@level='FAIL' and .='2']")
    assert not xml.xpath(".//test/kw[@name='Run Test']")


def test_setup_skipped(pr: PytestRobotTester):
    pr.run_and_assert_result(skipped=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test/kw[@name='Setup']/msg[@level='SKIP']")
    assert not xml.xpath(".//test/kw[@name='Run Test']")


def test_teardown_passes(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='1']")
    assert xml.xpath(".//test/kw[@name='Teardown']/msg[@level='INFO' and .='2']")


def test_teardown_fails(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result(passed=1, errors=1, exit_code=ExitCode.TESTS_FAILED)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test/kw[@name='Run Test']")
    assert xml.xpath(".//test/kw[@name='Teardown']/msg[@level='FAIL' and .='2']")


def test_error_moment(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='ERROR' and .='foo']")
    # make sure it didn't prevent the rest of the test from running
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='bar']")


def test_fixture_class_scope(pr: PytestRobotTester):
    if pr.xdist:
        # since the test is split into separate jobs, the fixture has to run multiple times
        pr.run_and_assert_result(passed=1, failed=1)
    else:
        pr.run_and_assert_result(passed=2)
    pr.assert_log_file_exists()


def test_fixture_module_scope(pytester_dir: PytesterDir):
    pr = PytestRobotTester(pytester=pytester_dir, xdist=None)
    pr.run_and_assert_result(passed=2)
    pr.assert_log_file_exists()


def test_error_moment_setup(pr: PytestRobotTester):
    pr.run_and_assert_result(errors=1, exit_code=ExitCode.TESTS_FAILED)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test/kw[@name='Setup']/msg[@level='ERROR' and .='foo']")
    assert xml.xpath(".//test/kw[@name='Setup']/msg[@level='INFO' and .='bar']")
    assert not xml.xpath(".//test/kw[@name='Run Test']")


def test_error_moment_teardown(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result(passed=1, errors=1, exit_code=ExitCode.TESTS_FAILED)
    # unlike pytest, teardown failures in robot count as a test failure
    assert_robot_total_stats(failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='baz']")
    assert xml.xpath(".//test/kw[@name='Teardown']/msg[@level='ERROR' and .='foo']")
    # make sure it didn't prevent the rest of the test from running
    assert xml.xpath(".//test/kw[@name='Teardown']/msg[@level='INFO' and .='bar']")


def test_error_moment_and_second_test(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1, failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        ".//test[@name='test_foo' and ./status[@status='FAIL']]/kw[@name='Run"
        " Test']/msg[@level='ERROR' and .='foo']"
    )
    assert xml.xpath(
        ".//test[@name='test_bar' and ./status[@status='PASS']]/kw[@name='Run"
        " Test']/msg[@level='INFO' and .='bar']"
    )


def test_error_moment_exitonerror(pr: PytestRobotTester):
    pr.run_and_assert_result("--robot-exitonerror", failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='ERROR' and .='foo']")
    # make sure it didn't prevent the rest of the test from running
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='bar']")


def test_error_moment_exitonerror_multiple_tests(pr: PytestRobotTester):
    # robot marks the remaining tests as failed but pytest never gets to actually run them
    if pr.xdist:
        pr.run_and_assert_result(failed=1, passed=1)
    else:
        pr.run_and_assert_assert_pytest_result("--robot-exitonerror", failed=1)
        # they run in separate workers so exitonerror won't work here
        assert_robot_total_stats(failed=2)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        ".//test[@name='test_foo' and ./status[@status='FAIL']]/kw[@name='Run"
        " Test']/msg[@level='ERROR' and .='foo']"
    )
    assert (
        bool(
            xml.xpath(
                ".//test[@name='test_bar']/status[@status='FAIL' and .='Error occurred"
                " and exit-on-error mode is in use.']"
            )
        )
        != pr.xdist
    )


def test_teardown_skipped(pr: PytestRobotTester):
    result = pr.run_pytest(subprocess=True)
    result.assert_outcomes(passed=1, skipped=1)
    assert result.ret == ExitCode.OK
    # unlike pytest, teardown skips in robot count as a test skip
    assert_robot_total_stats(skipped=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test/kw[@name='Run Test']")
    assert xml.xpath(".//test/kw[@name='Teardown']/msg[@level='SKIP']")


def test_fixture(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_module_docstring(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath("./suite/suite/doc[.='hello???']")


def test_test_case_docstring(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath("./suite/suite/test/doc[.='hello???']")


def test_keyword_decorator_docstring(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath(".//kw[@name='Run Test']/kw[@name='Foo']/doc[.='hie']")


def test_keyword_decorator_docstring_on_next_line(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath(".//kw[@name='Run Test']/kw[@name='Foo']/doc[.='hie']")


def test_keyword_decorator_args(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=2)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        ".//test[@name='test_no_truncation']//kw[@name='Run Test']/kw[@name='Foo' and ./arg[.='1']"
        " and ./arg[.='bar=True']]"
    )
    assert xml.xpath(
        ".//test[@name='test_truncation']//kw[@name='Run Test']/kw[@name='Foo' and"
        f" ./arg[.='{'a' * 50}...'] and ./arg[.='bar={'b' * 50}...']]"
    )


def test_keyword_decorator_custom_name_and_tags(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath(
        ".//kw[@name='Run Test']/kw[@name='foo bar' and ./tag['a'] and ./tag['b']]"
    )


def test_keyword_decorator_context_manager_that_doesnt_suppress(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='start']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='0']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='end']")
    assert xml.xpath("//kw[@name='Asdf' and ./status[@status='FAIL'] and ./msg[.='Exception']]")
    assert not xml.xpath("//msg[.='1']")


def test_keyword_decorator_context_manager_that_raises_in_exit(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='start']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='0']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='FAIL' and .='asdf']")
    assert not xml.xpath("//msg[.='1']")


def test_keyword_decorator_context_manager_that_raises_in_body_and_exit(pr: PytestRobotTester):
    pr.run_and_assert_result("--robot-loglevel", "DEBUG:INFO", failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='start']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='FAIL' and .='asdf']")
    assert xml.xpath(
        "//kw[@name='Asdf']/msg[@level='DEBUG' and contains(.,'Exception:"
        " fdsa\n\nDuring handling of the above exception, another exception"
        " occurred:') and contains(., 'Exception: asdf')]"
    )
    assert not xml.xpath("//msg[.='1']")


def test_keyword_decorator_returns_context_manager_that_isnt_used(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_keyword_decorator_try_except(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//kw[@name='Run Test' and ./status[@status='PASS']]/kw[@name='Bar' and"
        " ./status[@status='FAIL']]/msg[.='FooError']"
    )
    assert xml.xpath("//kw[@name='Run Test']/msg[.='hi']")


def test_keywordify_keyword_inside_context_manager(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//kw[@name='Raises' and ./arg[.=\"<class 'ZeroDivisionError'>\"]]/kw[@name='Asdf']"
    )


def test_keywordify_function(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath("//kw[@name='Fail' and ./arg[.='asdf']]")


def test_keywordify_context_manager(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath(
        "//kw[@name='Raises' and ./arg[.=\"<class 'ZeroDivisionError'>\"] and"
        " ./status[@status='PASS']]"
    )


def test_tags(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test[@name='test_tags']/tag[.='slow']")


def test_parameterized_tags(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(".//test[@name='test_tags']/tag[.='foo:bar']")


def test_keyword_names(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=2)
    pr.assert_log_file_exists()
    xml = output_xml()
    for index in range(2):
        assert xml.xpath(f".//test[@name='test_{index}']/kw[@name='Setup' and not(./arg)]")
        assert xml.xpath(f".//test[@name='test_{index}']/kw[@name='Run Test' and not(./arg)]")
        assert xml.xpath(f".//test[@name='test_{index}']/kw[@name='Teardown' and not(./arg)]")


def test_suite_variables(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_suite_variables_with_slash(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_variables_list(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_variables_not_in_scope_in_other_suites(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=2)
    pr.assert_log_file_exists()


def test_parametrize(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1, failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath("//test[@name='test_eval[1-8]']")
    assert xml.xpath("//test[@name='test_eval[6-6]']")


def test_unittest_class(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_robot_keyword_in_python_test(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_xfail_fails(pr: PytestRobotTester):
    pr.run_and_assert_result(xfailed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath("//kw[@name='Run Test' and ./msg[@level='SKIP' and .='xfail: asdf']]")


def test_xfail_passes(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath(
        "//kw[@name='Run Test' and ./msg[@level='FAIL' and .='[XPASS(strict)] asdf']]"
    )


def test_xfail_fails_no_reason(pr: PytestRobotTester):
    pr.run_and_assert_result(xfailed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath("//kw[@name='Run Test' and ./msg[@level='SKIP' and .='xfail']]")


def test_xfail_passes_no_reason(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath(
        "//kw[@name='Run Test' and ./msg[@level='FAIL' and .='[XPASS(strict)] ']]"
    )


def test_catch_errors_decorator(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result(passed=1, exit_code=ExitCode.INTERNAL_ERROR)
    pr.assert_log_file_exists()


def test_catch_errors_decorator_with_non_instance_method(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_no_tests_found_when_tests_exist(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result("asdfdsf", exit_code=ExitCode.USAGE_ERROR)


def test_assertion_fails(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath("//msg[@level='FAIL' and .='assert 1 == 2']")


def test_assertion_passes(pr: PytestRobotTester):
    pr.run_and_assert_result("-o", "enable_assertion_pass_hook=true", subprocess=True, passed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath(
        "//kw[@name='assert' and ./arg[.='left == right'] and ./status[@status='PASS']]"
        "/msg[@level='INFO' and .='1 == 1']"
    )


def test_assertion_fails_with_assertion_hook(pr: PytestRobotTester):
    pr.run_and_assert_result("-o", "enable_assertion_pass_hook=true", failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//kw[@name='assert' and ./arg[.='left == right'] and ./status[@status='FAIL']]"
        "/msg[@level='FAIL' and .='assert 1 == 2']"
    )
    # make sure the error was only logged once , since the exception gets re-raised after the
    # keyword is over we want to make sure it's not printed multiple times
    assert xpath(xml, "///msg[@level='FAIL']")


def test_nested_keyword_that_fails(pr: PytestRobotTester):
    pr.run_and_assert_result("-o", "enable_assertion_pass_hook=true", subprocess=True, failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath("//kw[@name='Bar']/msg[@level='FAIL' and .='asdf']")
    # make sure the error was only logged once , since the exception gets re-raised after the
    # keyword is over we want to make sure it's not printed multiple times
    assert xpath(xml, "///msg[@level='FAIL']")


def test_assertion_passes_hide_assert(pr: PytestRobotTester):
    pr.run_and_assert_result("-o", "enable_assertion_pass_hook=true", subprocess=True, passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//kw[@name='assert' and ./arg[.='left == right']]/msg[@level='INFO' and .='1 == 1']"
    )
    assert not xml.xpath("//kw[@name='assert']/arg[.='right == left']")
    assert xml.xpath(
        "//kw[@name='assert' and ./arg[.='right == right  # noqa: PLR0124']]/msg[@level='INFO' and "
        ".='1 == 1']"
    )


def test_assertion_passes_custom_messages(pr: PytestRobotTester):
    pr.run_and_assert_result("-o", "enable_assertion_pass_hook=true", subprocess=True, failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//kw[@name='assert' and ./arg[.='left == right']]/msg[@level='INFO' and .='1 == 1']"
    )
    assert xml.xpath(
        "//kw[@name='assert' and ./arg[.='does appear1'] and ./msg[@level='INFO' and .='assert "
        "right == left'] and ./msg[@level='INFO' and .='1 == 1']]"
    )
    assert xml.xpath(
        "//kw[@name='assert' and ./arg[.='right == \"wrong\"'] and ./msg[@level='FAIL' and .=\"does"
        " appear2\nassert 1 == 'wrong'\"]]"
    )


def test_assertion_passes_show_assert_when_no_assertions_in_robot_log(pr: PytestRobotTester):
    pr.run_and_assert_result(
        "-o",
        "enable_assertion_pass_hook=true",
        "--no-assertions-in-robot-log",
        subprocess=True,
        passed=1,
    )
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//kw[@name='assert' and ./arg[.='left == right']]/msg[@level='INFO' and .='1 == 1']"
    )
    assert not xml.xpath("//kw[@name='assert']/arg[.='right == left']")
    assert xml.xpath(
        "//kw[@name='assert' and ./arg[.='right == right']]/msg[@level='INFO' and " + ".='1 == 1']"
    )


def test_assertion_fails_with_fail_message_hide_assert(pr: PytestRobotTester):
    pr.run_and_assert_result("-o", "enable_assertion_pass_hook=true", subprocess=True, failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//kw[@name='assert' and ./arg[.='right == \"wrong\"']]/msg[@level='FAIL' and "
        ".=\"asdf\nassert 1 == 'wrong'\"]"
    )


def test_assertion_fails_with_description(pr: PytestRobotTester):
    pr.run_and_assert_result("-o", "enable_assertion_pass_hook=true", subprocess=True, failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//kw[@name='assert' and ./arg[.='asdf']]/msg[@level='FAIL' and .=\"assert 1 == 'wrong'\"]"
    )


def test_assertion_passes_hide_asserts_context_manager(pr: PytestRobotTester):
    pr.run_and_assert_result("-o", "enable_assertion_pass_hook=true", subprocess=True, passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath("//kw[@name='assert']/arg[.='1']")
    assert xml.xpath("//kw[@name='assert']/arg[.='right == left']")
    assert xml.xpath("//kw[@name='assert']/arg[.='2']")
    assert len(cast(list[XmlElement], xml.xpath("//kw[@name='assert']"))) == 3


def test_assertion_pass_hook_multiple_tests(pr: PytestRobotTester):
    pr.run_and_assert_result(
        "-o",
        "enable_assertion_pass_hook=true",
        "--robot-loglevel",
        "DEBUG:INFO",
        subprocess=True,
        passed=2,
    )
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//kw[@name='assert' and ./arg['left == right']]/msg[@level='INFO' and .='1 == 1']"
    )
    assert xml.xpath(
        "//kw[@name='assert' and ./arg['right == left']]/msg[@level='INFO' and .='1 == 1']"
    )


def test_keyword_and_pytest_raises(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath("//kw[@name='Raises']/kw[@name='Bar']/status[@status='FAIL']")


def test_keyword_raises(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    assert output_xml().xpath(
        "//kw[@name='Bar' and ./status[@status='FAIL'] and ./msg[.='FooError']]"
    )


def test_as_keyword_context_manager_try_except(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath("//kw[@name='hi' and ./status[@status='FAIL']]/msg[.='FooError']")
    assert xml.xpath("//kw[@name='Run Test']/msg[.='2']")


def test_as_keyword_args_and_kwargs(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath("//kw[@name='asdf']/arg[.='a']")
    assert xml.xpath("//kw[@name='asdf']/arg[.='b']")
    assert xml.xpath("//kw[@name='asdf']/arg[.='c=d']")
    assert xml.xpath("//kw[@name='asdf']/arg[.='e=f']")


def test_invalid_fixture(pr: PytestRobotTester):
    pr.run_and_assert_result(errors=1, exit_code=ExitCode.TESTS_FAILED)
    pr.assert_log_file_exists()
    assert not output_xml().xpath("//*[contains(., 'Unknown exception type appeared')]")


def test_pytest_runtest_protocol_session_hook(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_pytest_runtest_protocol_item_hook(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_pytest_runtest_protocol_hook_in_different_suite(pr: PytestRobotTester):
    pr.run_and_assert_result(
        "-m",
        "asdf",
        # the assertion_pass hook relies on this functionality so we need to make sure that works
        # correctly too
        "-o",
        "enable_assertion_pass_hook=true",
        passed=1,
    )
    pr.assert_log_file_exists()
    assert xpath(
        output_xml(), "//kw[@name='assert' and ./arg[.='True'] and ./status[@status='PASS']]"
    )


def test_traceback(pr: PytestRobotTester):
    pr.run_and_assert_result("--robot-loglevel", "DEBUG:INFO", failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xml.xpath(
        "//msg[@level='DEBUG' and contains(., 'in test_foo') and contains(., 'in asdf')]"
    )


def test_config_file_in_different_location(pr: PytestRobotTester):
    pr.run_and_assert_result("-c", "asdf/tox.ini", passed=1)
    pr.assert_log_file_exists()


def test_config_file_and_cwd_in_different_location(pr: PytestRobotTester, monkeypatch: MonkeyPatch):
    monkeypatch.chdir(pr.pytester.path / "foo")
    pr.run_and_assert_result("-c", "../config/tox.ini", "../tests", passed=1)
    pr.assert_log_file_exists()


def test_xdist_n_0(pytester_dir: PytesterDir):
    pr = PytestRobotTester(pytester=pytester_dir, xdist=0)
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_two_tests_specified_by_full_path(pr: PytestRobotTester):
    file_name = f"{test_two_tests_specified_by_full_path.__name__}.py"
    pr.run_and_assert_result(f"{file_name}::test_foo", f"{file_name}::test_bar", passed=2)
    pr.assert_log_file_exists()


def test_two_tests_specified_by_full_path_in_different_files(pr: PytestRobotTester):
    pr.run_and_assert_result("test_foo.py::test_foo", "test_bar.py::test_bar", passed=2)
    pr.assert_log_file_exists()
    # test that the combined top-level suite name worked:
    xml = output_xml()
    # we don't know what order they will be in:
    assert xpath(xml, "/robot/suite[@name='Test Bar & Test Foo' or @name='Test Foo & Test Bar']")
    # make sure the metadata with the original suite names were deleted
    assert not xml.xpath("//meta")


def test_assertion_rewritten_in_conftest_when_assertion_hook_enabled(pr: PytestRobotTester):
    pr.run_and_assert_result("-o", "enable_assertion_pass_hook=true", subprocess=True, passed=1)
    pr.assert_log_file_exists()


class TestStackTraces:
    @staticmethod
    def parse_stack_trace(stack: str) -> dict[int, str]:
        result: dict[int, str] = {}
        for line in stack.split("\n"):
            match = search(r"\s+File \".*\", line (\d+), in (.*)", line)
            if match:
                result[int(match[1])] = match[2]
        return result

    @classmethod
    def test_trace_ricing(cls, pr: PytestRobotTester):
        pr.run_and_assert_result("--robot-loglevel", "DEBUG:INFO", failed=1)
        pr.assert_log_file_exists()
        xml = output_xml()
        result = xpath(
            xml, "//msg[@level='DEBUG' and contains(., 'Traceback (most recent call last)')]"
        ).text

        assert result
        assert "Exception: THIS!" in result
        assert cls.parse_stack_trace(result) == {5: "test_0"}

    @classmethod
    def test_full_stack_keyword_decorator(cls, pr: PytestRobotTester):
        pr.run_and_assert_result("--robot-loglevel", "DEBUG", failed=1)
        pr.assert_log_file_exists()
        xml = output_xml()
        result = xpath(
            xml, "//msg[@level='DEBUG' and contains(., 'Traceback (most recent call last)')]"
        ).text
        assert result, "failed to find xpath"
        assert cls.parse_stack_trace(result) == {12: "test_keyword", 8: "bar"}

    @classmethod
    def test_full_stack_keyword_context_manager(cls, pr: PytestRobotTester):
        pr.run_and_assert_result("--robot-loglevel", "DEBUG", failed=1)
        pr.assert_log_file_exists()
        xml = output_xml()
        result = xpath(
            xml, "//msg[@level='DEBUG' and contains(., 'Traceback (most recent call last)')]"
        ).text
        assert result, "no text in xpath"
        assert cls.parse_stack_trace(result) == {17: "test_as_keyword", 8: "foo", 13: "bar"}


def test_ansi(pr: PytestRobotTester):
    pr.run_and_assert_result("-vv", "--color=yes", failed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    assert xpath(
        xml,
        """//msg[@level='FAIL' and @html='true'
        and contains(., "assert [1, 2, 3] == [1, '&lt;div&gt;asdf&lt;/div&gt;', 3]")
        and contains(., 'span style="color: #5c5cff">2</span><span style="color: #7f7f7f"')
        ]""",
    ).text
    assert xml.xpath("""//status[@status='FAIL' and .="\
assert [1, 2, 3] == [1, '<div>asdf</div>', 3]
  
  At index 1 diff: 2 != '<div>asdf</div>'
  
  Full diff:
    [
        1,
  -     '<div>asdf</div>',
  +     2,
        3,
    ]"
    ]""")


def test_set_log_level(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = output_xml()
    # on robot 6 this is logged as INFO and on robot 7 it's logged as DEBUG
    assert xml.xpath("//msg[.='Log level changed from INFO to DEBUG.']")
    assert xml.xpath("//msg[@level='DEBUG' and .='hello???']")


def test_class_has_separate_suite(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=3)
    pr.assert_log_file_exists()
    xml = output_xml()
    top_level_suite = xpath(xml, "//suite[@name='Test Class Has Separate Suite']")
    assert top_level_suite.count_children() == 3  # suite, test, status
    assert xpath(top_level_suite, "./test[@name='test_foo']")

    class_suite = xpath(top_level_suite, "./suite[@name='TestBar']")
    assert class_suite.count_children() == 3  # 2 tests and a status
    assert xpath(class_suite, "./test[@name='test_fooasdf']")
    assert xpath(class_suite, "./test[@name='test_bar']")


def test_nested_class(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=3)
    pr.assert_log_file_exists()
    xml = output_xml()
    top_level_suite = xpath(xml, "//suite[@name='Test Nested Class']")
    assert top_level_suite.count_children() == 3  # suite, test, status
    assert xpath(top_level_suite, "./test[@name='test_foo']")

    class_suite = xpath(top_level_suite, "./suite[@name='TestBar']")
    assert class_suite.count_children() == 3  # suite, test, status
    assert xpath(class_suite, "./test[@name='test_bar']")

    nested_class_suite = xpath(class_suite, "./suite[@name='TestBaz']")
    assert nested_class_suite.count_children() == 2  # test, status
    assert xpath(nested_class_suite, "./test[@name='test_baz']")


def test_class_separate_files(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=4)
    pr.assert_log_file_exists()
    xml = output_xml()
    for file_number in (1, 2):
        top_level_suite = xpath(xml, f"//suite[@name='Test Suite{file_number}']")
        assert top_level_suite.count_children() == 3  # suite, test, status
        assert xpath(top_level_suite, f"./test[@name='test_foo{file_number}']")

        class_suite = xpath(top_level_suite, f"./suite[@name='TestClass{file_number}']")
        assert class_suite.count_children() == 2  # test and status
        assert xpath(class_suite, f"./test[@name='test_bar{file_number}']")


def test_python_file_doesnt_get_parsed_as_robot_file(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result("--collect-only", exit_code=ExitCode.NO_TESTS_COLLECTED)


def test_class_three_tests_one_fail(pr: PytestRobotTester):
    """this test is for an xdist issue. needs to have one more tests than there are workers"""
    pr.run_and_assert_result(passed=2, failed=1)
    pr.assert_log_file_exists()


def test_console_summary(pr: PytestRobotTester):
    result = pr.run_pytest("--robot-outputdir=a", "--robot-log=b", subprocess=True)
    path = pr.pytester.path / "a" / "b"
    assert re.search(
        rf"""

Robot Framework Log File:
Log:     {re.escape(str(path))}
Log URI: {re.escape(path.as_uri())}
""",
        "\n".join(result.outlines),
    )
    result = pr.run_pytest("--robot-log=", subprocess=True)
    assert "Robot Framework Output Files:" not in result.outlines


def test_console_summary_collect_only(pr: PytestRobotTester):
    result = pr.run_pytest("--robot-outputdir=a", "--robot-log=b", "--collect-only")
    assert "Robot Framework Log File" not in "\n".join(result.outlines)


def test_console_output(pr: PytestRobotTester):
    if pr.xdist:
        result = pr.run_pytest("--capture=no")
        assert "Output:" not in "\n".join(result.outlines)
    else:
        result = pr.run_pytest("--collect-only")
        assert "0 tests, 0 passed, 0 failed" not in result.outlines
        assert "Output:  None" not in result.outlines

        result = pr.run_pytest("--capture=no", "--collect-only")
        assert "0 tests, 0 passed, 0 failed" not in result.outlines
        assert "Output:  None" not in result.outlines

        result = pr.run_pytest("--capture=no")
        if sys.platform == "win32" and running_on_ci():
            # don't ask
            assert "I'm console ?" in result.outlines
        else:
            assert "I'm console 🚽" in result.outlines
        assert "[ WARN ] I'm warning" in result.errlines

        result = pr.run_pytest("--quiet", "--capture=no", "--robot-console=verbose")
        if robot_6:
            assert f"Output:  {pr.pytester.path / 'output.xml'}" in result.outlines
        else:
            assert "Output:  output.xml" in result.outlines


def test_exitfirst(pr: PytestRobotTester):
    if pr.xdist:
        skip(
            "--exitfirst doesn't work with xdist. https://github.com/pytest-dev/pytest-xdist/issues/420"
        )
    pr.run_and_assert_result("-x", failed=1, skipped=1)


def test_maxfail(pr: PytestRobotTester):
    if pr.xdist:
        skip(
            "--maxfail doesn't work with xdist. https://github.com/pytest-dev/pytest-xdist/issues/868"
        )
    pr.run_and_assert_result("--maxfail=2", failed=2, skipped=1)
