from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from pytest import ExitCode

from pytest_robotframework._internal.errors import UserError

if TYPE_CHECKING:
    from conftest import PytestRobotTester


def test_one_test_passes(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_one_test_fails(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()


def test_one_test_skipped(pr: PytestRobotTester):
    pr.run_and_assert_result(skipped=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath(
        "./suite//test[@name='test_one_test_skipped']/kw[@type='SETUP']/msg[@level='SKIP']"
    )


def test_two_tests_one_fail_one_pass(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1, failed=1)
    pr.assert_log_file_exists()


def test_two_tests_two_files_one_fail_one_pass(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1, failed=1)
    pr.assert_log_file_exists()


def test_two_tests_with_same_name_one_fail_one_pass(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1, failed=1)
    pr.assert_log_file_exists()


def test_suites(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath(
        "./suite/suite[@name='Suite1']/suite[@name='Test"
        " Asdf']/test[@name='test_func1']"
    )


def test_nested_suites(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=2, failed=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(
        "./suite/suite[@name='Suite1']/suite[@name='Suite2']/suite[@name='Test"
        " Asdf']/test[@name='test_func1']"
    )
    assert xml.xpath(
        "./suite/suite[@name='Suite1']/suite[@name='Suite3']/suite[@name='Test"
        " Asdf2']/test[@name='test_func2']"
    )
    assert xml.xpath("./suite/suite[@name='Test Top Level']/test[@name='test_func1']")


def test_robot_options_variable(pr: PytestRobotTester):
    results_path = pr.pytester.path / "results"
    env_variable = "ROBOT_OPTIONS"
    try:
        os.environ[env_variable] = f"-d {results_path}"
        result = pr.pytester.runpytest_subprocess()
    finally:
        del os.environ[env_variable]
    result.assert_outcomes(passed=1)
    assert (results_path / "log.html").exists()


def test_robot_options_merge_listeners(pr: PytestRobotTester):
    result = pr.pytester.runpytest_subprocess(
        "--robotargs", f"--listener {pr.pytester.path / 'Listener.py'}"
    )
    result.assert_outcomes(passed=1)
    pr.assert_log_file_exists()


def test_robot_options_variable_merge_listeners(pr: PytestRobotTester):
    env_variable = "ROBOT_OPTIONS"
    try:
        os.environ[env_variable] = f"--listener {pr.pytester.path / 'Listener.py'}"
        result = pr.pytester.runpytest_subprocess()
    finally:
        del os.environ[env_variable]
    result.assert_outcomes(passed=1)
    pr.assert_log_file_exists()


def test_robot_modify_args_hook(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_robot_modify_args_hook_collect_only(pr: PytestRobotTester):
    result = pr.pytester.runpytest_subprocess("--collect-only")
    assert result.parseoutcomes() == {"test": 1}
    assert not (pr.pytester.path / "log.html").exists()


def test_listener_calls_log_file(pr: PytestRobotTester):
    result = pr.pytester.runpytest_subprocess(
        "--robotargs", f"--listener {pr.pytester.path / 'Listener.py'}"
    )
    result.assert_outcomes(passed=1)
    pr.assert_log_file_exists()
    assert Path("hi").exists()


def test_doesnt_run_when_collecting(pr: PytestRobotTester):
    result = pr.pytester.runpytest_subprocess("--collect-only")
    result.assert_outcomes()
    assert not (pr.pytester.path / "log.html").exists()


# TODO: this test doesnt actually test anything
# https://github.com/DetachHead/pytest-robotframework/issues/61
def test_collect_only_nested_suites(pr: PytestRobotTester):
    result = pr.pytester.runpytest_subprocess("--collect-only")
    assert result.parseoutcomes() == {"tests": 2}
    assert "<Function test_func2>" in (line.strip() for line in result.outlines)


def test_correct_items_collected_when_collect_only(pr: PytestRobotTester):
    result = pr.pytester.runpytest_subprocess("--collect-only", "test_bar.py")
    assert result.parseoutcomes() == {"test": 1}
    assert "<Function test_func2>" in (line.strip() for line in result.outlines)


def test_setup_passes(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(".//test/kw[@name='Setup']/msg[@level='INFO' and .='2']")
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='1']")


def test_setup_fails(pr: PytestRobotTester):
    pr.run_and_assert_result(errors=1, exit_code=ExitCode.TESTS_FAILED)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(".//test/kw[@name='Setup']/msg[@level='FAIL' and .='2']")
    assert not xml.xpath(".//test/kw[@name='Run Test']")


def test_setup_skipped(pr: PytestRobotTester):
    pr.run_and_assert_result(skipped=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(".//test/kw[@name='Setup']/msg[@level='SKIP']")
    assert not xml.xpath(".//test/kw[@name='Run Test']")


def test_teardown_passes(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='1']")
    assert xml.xpath(".//test/kw[@name='Teardown']/msg[@level='INFO' and .='2']")


def test_teardown_fails(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result(
        passed=1, errors=1, exit_code=ExitCode.TESTS_FAILED
    )
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(".//test/kw[@name='Run Test']")
    assert xml.xpath(".//test/kw[@name='Teardown']/msg[@level='FAIL' and .='2']")


def test_error_moment(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='ERROR' and .='foo']")
    # make sure it didn't prevent the rest of the test from running
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='bar']")


def test_fixture_scope(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=2)
    pr.assert_log_file_exists()


def test_error_moment_setup(pr: PytestRobotTester):
    pr.run_and_assert_result(errors=1, exit_code=ExitCode.TESTS_FAILED)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(".//test/kw[@name='Setup']/msg[@level='ERROR' and .='foo']")
    assert xml.xpath(".//test/kw[@name='Setup']/msg[@level='INFO' and .='bar']")
    assert not xml.xpath(".//test/kw[@name='Run Test']")


def test_error_moment_teardown(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result(
        passed=1, errors=1, exit_code=ExitCode.TESTS_FAILED
    )
    # unlike pytest, teardown failures in robot count as a test failure
    pr.assert_robot_total_stats(failed=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='baz']")
    assert xml.xpath(".//test/kw[@name='Teardown']/msg[@level='ERROR' and .='foo']")
    # make sure it didn't prevent the rest of the test from running
    assert xml.xpath(".//test/kw[@name='Teardown']/msg[@level='INFO' and .='bar']")


def test_error_moment_and_second_test(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1, failed=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(
        ".//test[@name='test_foo' and ./status[@status='FAIL']]/kw[@name='Run"
        " Test']/msg[@level='ERROR' and .='foo']"
    )
    assert xml.xpath(
        ".//test[@name='test_bar' and ./status[@status='PASS']]/kw[@name='Run"
        " Test']/msg[@level='INFO' and .='bar']"
    )


def test_error_moment_exitonerror(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1, pytest_args=["--robotargs=--exitonerror"])
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='ERROR' and .='foo']")
    # make sure it didn't prevent the rest of the test from running
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='bar']")


def test_error_moment_exitonerror_multiple_tests(pr: PytestRobotTester):
    pr.run_and_assert_assert_pytest_result(
        failed=1, pytest_args=["--robotargs=--exitonerror"]
    )
    # robot marks the remaining tests as failed but pytest never gets to actually run them
    pr.assert_robot_total_stats(failed=2)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(
        ".//test[@name='test_foo' and ./status[@status='FAIL']]/kw[@name='Run"
        " Test']/msg[@level='ERROR' and .='foo']"
    )
    assert xml.xpath(
        ".//test[@name='test_bar']/status[@status='FAIL' and .='Error occurred and"
        " exit-on-error mode is in use.']"
    )


def test_teardown_skipped(pr: PytestRobotTester):
    result = pr.pytester.runpytest_subprocess()
    result.assert_outcomes(passed=1, skipped=1)
    # unlike pytest, teardown skips in robot count as a test skip
    pr.assert_robot_total_stats(skipped=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(".//test/kw[@name='Run Test']")
    assert xml.xpath(".//test/kw[@name='Teardown']/msg[@level='SKIP']")


def test_fixture(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_module_docstring(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath("./suite/suite/doc[.='hello???']")


def test_test_case_docstring(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath("./suite/suite/test/doc[.='hello???']")


def test_keyword_decorator_docstring(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath(".//kw[@name='Run Test']/kw[@name='Foo']/doc[.='hie']")


def test_keyword_decorator_docstring_on_next_line(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath(".//kw[@name='Run Test']/kw[@name='Foo']/doc[.='hie']")


def test_keyword_decorator_args(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath(
        ".//kw[@name='Run Test']/kw[@name='Foo' and ./arg[.='1'] and"
        " ./arg[.='bar=True']]"
    )


def test_keyword_decorator_custom_name_and_tags(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath(
        ".//kw[@name='Run Test']/kw[@name='foo bar' and ./tag['a'] and ./tag['b']]"
    )


def test_keyword_decorator_context_manager_that_doesnt_suppress(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='start']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='0']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='end']")
    assert xml.xpath(
        "//kw[@name='Asdf' and ./status[@status='FAIL'] and ./msg[.='Exception']]"
    )
    assert not xml.xpath("//msg[.='1']")


def test_keyword_decorator_context_manager_that_raises_in_exit(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='start']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='0']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='FAIL' and .='asdf']")
    assert not xml.xpath("//msg[.='1']")


def test_keyword_decorator_context_manager_that_raises_in_body_and_exit(
    pr: PytestRobotTester,
):
    pr.run_and_assert_result(
        pytest_args=["--robotargs", "--loglevel DEBUG:INFO"], failed=1
    )
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='start']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='FAIL' and .='asdf']")
    assert xml.xpath(
        "//kw[@name='Asdf']/msg[@level='DEBUG' and contains(.,'Exception:"
        " fdsa\n\nDuring handling of the above exception, another exception"
        " occurred:') and contains(., 'Exception: asdf')]"
    )
    assert not xml.xpath("//msg[.='1']")


def test_keyword_decorator_returns_context_manager_that_isnt_used(
    pr: PytestRobotTester,
):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_keyword_decorator_try_except(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(
        "//kw[@name='Run Test' and ./status[@status='PASS']]/kw[@name='Bar' and"
        " ./status[@status='FAIL']]/msg[.='FooError']"
    )
    assert xml.xpath("//kw[@name='Run Test']/msg[.='hi']")


def test_keywordify_keyword_inside_context_manager(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(
        "//kw[@name='Raises' and ./arg[.=\"<class"
        " 'ZeroDivisionError'>\"]]/kw[@name='Asdf']"
    )


def test_keywordify_function(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath("//kw[@name='Fail' and ./arg[.='asdf']]")


def test_keywordify_context_manager(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath(
        "//kw[@name='Raises' and ./arg[.=\"<class 'ZeroDivisionError'>\"] and"
        " ./status[@status='PASS']]"
    )


def test_tags(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(".//test[@name='test_tags']/tag[.='slow']")


def test_parameterized_tags(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(".//test[@name='test_tags']/tag[.='foo:bar']")


def test_keyword_names(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=2)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    for index in range(2):
        assert xml.xpath(
            f".//test[@name='test_{index}']/kw[@name='Setup' and not(./arg)]"
        )
        assert xml.xpath(
            f".//test[@name='test_{index}']/kw[@name='Run Test' and not(./arg)]"
        )
        assert xml.xpath(
            f".//test[@name='test_{index}']/kw[@name='Teardown' and not(./arg)]"
        )


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
    xml = pr.output_xml()
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
    assert pr.output_xml().xpath(
        "//kw[@name='Run Test' and ./msg[@level='SKIP' and .='xfail: asdf']]"
    )


def test_xfail_passes(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath(
        "//kw[@name='Run Test' and ./msg[@level='FAIL' and .='[XPASS(strict)] asdf']]"
    )


def test_xfail_fails_no_reason(pr: PytestRobotTester):
    pr.run_and_assert_result(xfailed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath(
        "//kw[@name='Run Test' and ./msg[@level='SKIP' and .='xfail']]"
    )


def test_xfail_passes_no_reason(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath(
        "//kw[@name='Run Test' and ./msg[@level='FAIL' and .='[XPASS(strict)] ']]"
    )


def test_listener_decorator(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_listener_decorator_registered_too_late(pr: PytestRobotTester):
    # all the other tests run pytest in subprocess mode but we keep this one as inprocess to check
    # for https://github.com/DetachHead/pytest-robotframework/issues/38
    result = pr.pytester.runpytest()
    result.assert_outcomes(errors=1)
    # pytest failed before test was collected so nothing in the robot run
    pr.assert_robot_total_stats()
    pr.assert_log_file_exists()
    assert (
        f"E   {UserError.__module__}.{UserError.__qualname__}: Listener cannot be"
        " registered because robot has already started running. make sure it's defined"
        " in a `conftest.py` file" in result.outlines
    )


def test_catch_errors_decorator(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1, exit_code=ExitCode.INTERNAL_ERROR)
    pr.assert_log_file_exists()


def test_catch_errors_decorator_with_non_instance_method(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_no_tests_found_when_tests_exist(pr: PytestRobotTester):
    pr.run_and_assert_result(pytest_args=["asdfdsf"], exit_code=ExitCode.INTERNAL_ERROR)
    pr.assert_log_file_exists()


def test_assertion_fails(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath("//msg[@level='FAIL' and .='assert 1 == 2']")


def test_assertion_passes(pr: PytestRobotTester):
    pr.run_and_assert_result(
        pytest_args=[
            "-o",
            "enable_assertion_pass_hook=true",
            "--robotargs",
            "--loglevel DEBUG:INFO",
        ],
        subprocess=True,
        passed=1,
    )
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath(
        "//kw[@name='assert' and ./arg['left == right']]/msg[@level='INFO' and"
        " .='1 == 1']"
    )


def test_assertion_pass_hook_multiple_tests(pr: PytestRobotTester):
    pr.run_and_assert_result(
        pytest_args=[
            "-o",
            "enable_assertion_pass_hook=true",
            "--robotargs",
            "--loglevel DEBUG:INFO",
        ],
        subprocess=True,
        passed=2,
    )
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(
        "//kw[@name='assert' and ./arg['left == right']]/msg[@level='INFO' and"
        " .='1 == 1']"
    )
    assert xml.xpath(
        "//kw[@name='assert' and ./arg['right == left']]/msg[@level='INFO' and"
        " .='1 == 1']"
    )


def test_keyword_and_pytest_raises(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath(
        "//kw[@name='Raises']/kw[@name='Bar']/status[@status='FAIL']"
    )


def test_keyword_raises(pr: PytestRobotTester):
    pr.run_and_assert_result(failed=1)
    pr.assert_log_file_exists()
    assert pr.output_xml().xpath(
        "//kw[@name='Bar' and ./status[@status='FAIL'] and ./msg[.='FooError']]"
    )


def test_as_keyword_context_manager_try_except(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath("//kw[@name='hi' and ./status[@status='FAIL']]/msg[.='FooError']")
    assert xml.xpath("//kw[@name='Run Test']/msg[.='2']")


def test_as_keyword_args_and_kwargs(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath("//kw[@name='asdf']/arg[.='a']")
    assert xml.xpath("//kw[@name='asdf']/arg[.='b']")
    assert xml.xpath("//kw[@name='asdf']/arg[.='c=d']")
    assert xml.xpath("//kw[@name='asdf']/arg[.='e=f']")


def test_invalid_fixture(pr: PytestRobotTester):
    pr.run_and_assert_result(errors=1, exit_code=ExitCode.TESTS_FAILED)
    pr.assert_log_file_exists()
    assert not pr.output_xml().xpath(
        "//*[contains(., 'Unknown exception type appeared')]"
    )


def test_pytest_runtest_protocol_session_hook(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_pytest_runtest_protocol_item_hook(pr: PytestRobotTester):
    pr.run_and_assert_result(passed=1)
    pr.assert_log_file_exists()


def test_pytest_runtest_protocol_hook_in_different_suite(pr: PytestRobotTester):
    pr.run_and_assert_result(pytest_args=["-m", "asdf"], passed=1)
    pr.assert_log_file_exists()


def test_traceback(pr: PytestRobotTester):
    pr.run_and_assert_result(
        pytest_args=["--robotargs", "--loglevel DEBUG:INFO"], failed=1
    )
    pr.assert_log_file_exists()
    xml = pr.output_xml()
    assert xml.xpath(
        "//msg[@level='DEBUG' and contains(., 'in test_foo') and contains(., 'in"
        " asdf')]"
    )


def test_config_file_in_different_location(pr: PytestRobotTester):
    pr.run_and_assert_result(pytest_args=["-c", "asdf/tox.ini"], passed=1)
    pr.assert_log_file_exists()
