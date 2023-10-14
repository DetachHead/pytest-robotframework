from __future__ import annotations

import os
from pathlib import Path

from pytest import ExitCode

from tests.utils import (
    PytesterDir,
    assert_log_file_exists,
    assert_robot_total_stats,
    output_xml,
    run_and_assert_assert_pytest_result,
    run_and_assert_result,
)


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
        "./suite//test[@name='test_one_test_skipped']/kw[@type='SETUP']/msg[@level='SKIP']"
    )


def test_two_tests_one_fail_one_pass(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1, failed=1)
    assert_log_file_exists(pytester_dir)


def test_two_tests_two_files_one_fail_one_pass(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1, failed=1)
    assert_log_file_exists(pytester_dir)


def test_two_tests_with_same_name_one_fail_one_pass(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1, failed=1)
    assert_log_file_exists(pytester_dir)


def test_suites(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        "./suite/suite[@name='Suite1']/suite[@name='Test"
        " Asdf']/test[@name='test_func1']"
    )


def test_nested_suites(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=2, failed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        "./suite/suite[@name='Suite1']/suite[@name='Suite2']/suite[@name='Test"
        " Asdf']/test[@name='test_func1']"
    )
    assert xml.xpath(
        "./suite/suite[@name='Suite1']/suite[@name='Suite3']/suite[@name='Test"
        " Asdf2']/test[@name='test_func2']"
    )
    assert xml.xpath("./suite/suite[@name='Test Top Level']/test[@name='test_func1']")


def test_robot_args(pytester_dir: PytesterDir):
    results_path = pytester_dir.path / "results"
    result = pytester_dir.runpytest("--robotargs", f"-d {results_path}")
    result.assert_outcomes(passed=1)
    assert (results_path / "log.html").exists()


def test_robot_options_variable(pytester_dir: PytesterDir):
    results_path = pytester_dir.path / "results"
    env_variable = "ROBOT_OPTIONS"
    try:
        os.environ[env_variable] = f"-d {results_path}"
        result = pytester_dir.runpytest()
    finally:
        del os.environ[env_variable]
    result.assert_outcomes(passed=1)
    assert (results_path / "log.html").exists()


def test_robot_options_merge_listeners(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest(
        "--robotargs", f"--listener {pytester_dir.path / 'Listener.py'}"
    )
    result.assert_outcomes(passed=1)
    assert_log_file_exists(pytester_dir)


def test_robot_options_variable_merge_listeners(pytester_dir: PytesterDir):
    env_variable = "ROBOT_OPTIONS"
    try:
        os.environ[env_variable] = f"--listener {pytester_dir.path / 'Listener.py'}"
        result = pytester_dir.runpytest()
    finally:
        del os.environ[env_variable]
    result.assert_outcomes(passed=1)
    assert_log_file_exists(pytester_dir)


def test_robot_modify_args_hook(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)


def test_robot_modify_args_hook_collect_only(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest("--collect-only")
    assert result.parseoutcomes() == {"test": 1}
    assert not (pytester_dir.path / "log.html").exists()


def test_listener_calls_log_file(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest(
        "--robotargs", f"--listener {pytester_dir.path / 'Listener.py'}"
    )
    result.assert_outcomes(passed=1)
    assert_log_file_exists(pytester_dir)
    assert Path("hi").exists()


def test_doesnt_run_when_collecting(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest("--collect-only")
    result.assert_outcomes()
    assert not (pytester_dir.path / "log.html").exists()


# TODO: this test doesnt actually test anything
# https://github.com/DetachHead/pytest-robotframework/issues/61
def test_collect_only_nested_suites(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest("--collect-only")
    assert result.parseoutcomes() == {"tests": 2}
    assert "<Function test_func2>" in (line.strip() for line in result.outlines)


def test_correct_items_collected_when_collect_only(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest("--collect-only", "test_bar.py")
    assert result.parseoutcomes() == {"test": 1}
    assert "<Function test_func2>" in (line.strip() for line in result.outlines)


def test_setup_passes(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(".//test/kw[@name='Setup']/msg[@level='INFO' and .='2']")
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='1']")


def test_setup_fails(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, errors=1, exit_code=ExitCode.TESTS_FAILED)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        ".//test/kw[@name='Setup']/msg[@level='FAIL' and .='Exception: 2']"
    )
    assert not xml.xpath(".//test/kw[@name='Run Test']")


def test_setup_skipped(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, skipped=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(".//test/kw[@name='Setup']/msg[@level='SKIP']")
    assert not xml.xpath(".//test/kw[@name='Run Test']")


def test_teardown_passes(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='1']")
    assert xml.xpath(".//test/kw[@name='Teardown']/msg[@level='INFO' and .='2']")


def test_teardown_fails(pytester_dir: PytesterDir):
    run_and_assert_assert_pytest_result(
        pytester_dir, passed=1, errors=1, exit_code=ExitCode.TESTS_FAILED
    )
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(".//test/kw[@name='Run Test']")
    assert xml.xpath(
        ".//test/kw[@name='Teardown']/msg[@level='FAIL' and .='Exception: 2']"
    )


def test_error_moment(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, failed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='ERROR' and .='foo']")
    # make sure it didn't prevent the rest of the test from running
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='bar']")


def test_error_moment_setup(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, errors=1, exit_code=ExitCode.TESTS_FAILED)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(".//test/kw[@name='Setup']/msg[@level='ERROR' and .='foo']")
    assert xml.xpath(".//test/kw[@name='Setup']/msg[@level='INFO' and .='bar']")
    assert not xml.xpath(".//test/kw[@name='Run Test']")


def test_error_moment_teardown(pytester_dir: PytesterDir):
    run_and_assert_assert_pytest_result(
        pytester_dir, passed=1, errors=1, exit_code=ExitCode.TESTS_FAILED
    )
    # unlike pytest, teardown failures in robot count as a test failure
    assert_robot_total_stats(pytester_dir, failed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='baz']")
    assert xml.xpath(".//test/kw[@name='Teardown']/msg[@level='ERROR' and .='foo']")
    # make sure it didn't prevent the rest of the test from running
    assert xml.xpath(".//test/kw[@name='Teardown']/msg[@level='INFO' and .='bar']")


def test_error_moment_and_second_test(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1, failed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        ".//test[@name='test_foo' and ./status[@status='FAIL']]/kw[@name='Run"
        " Test']/msg[@level='ERROR' and .='foo']"
    )
    assert xml.xpath(
        ".//test[@name='test_bar' and ./status[@status='PASS']]/kw[@name='Run"
        " Test']/msg[@level='INFO' and .='bar']"
    )


def test_error_moment_exitonerror(pytester_dir: PytesterDir):
    run_and_assert_result(
        pytester_dir, failed=1, pytest_args=["--robotargs=--exitonerror"]
    )
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='ERROR' and .='foo']")
    # make sure it didn't prevent the rest of the test from running
    assert xml.xpath(".//test/kw[@name='Run Test']/msg[@level='INFO' and .='bar']")


def test_error_moment_exitonerror_multiple_tests(pytester_dir: PytesterDir):
    run_and_assert_assert_pytest_result(
        pytester_dir, failed=1, pytest_args=["--robotargs=--exitonerror"]
    )
    # robot marks the remaining tests as failed but pytest never gets to actually run them
    assert_robot_total_stats(pytester_dir, failed=2)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        ".//test[@name='test_foo' and ./status[@status='FAIL']]/kw[@name='Run"
        " Test']/msg[@level='ERROR' and .='foo']"
    )
    assert xml.xpath(
        ".//test[@name='test_bar']/status[@status='FAIL' and .='Error occurred and"
        " exit-on-error mode is in use.']"
    )


def test_teardown_skipped(pytester_dir: PytesterDir):
    result = pytester_dir.runpytest()
    result.assert_outcomes(passed=1, skipped=1)
    # unlike pytest, teardown skips in robot count as a test skip
    assert_robot_total_stats(pytester_dir, skipped=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(".//test/kw[@name='Run Test']")
    assert xml.xpath(".//test/kw[@name='Teardown']/msg[@level='SKIP']")


def test_fixture(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)


def test_module_docstring(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath("./suite/suite/doc[.='hello???']")


def test_test_case_docstring(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath("./suite/suite/test/doc[.='hello???']")


def test_keyword_decorator_docstring(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        ".//kw[@name='Run Test']/kw[@name='Foo']/doc[.='hie']"
    )


def test_keyword_decorator_docstring_on_next_line(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        ".//kw[@name='Run Test']/kw[@name='Foo']/doc[.='hie']"
    )


def test_keyword_decorator_args(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        ".//kw[@name='Run Test']/kw[@name='Foo' and ./arg[.='1'] and"
        " ./arg[.='bar=True']]"
    )


def test_keyword_decorator_custom_name_and_tags(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        ".//kw[@name='Run Test']/kw[@name='foo bar' and ./tag['a'] and ./tag['b']]"
    )


def test_keyword_decorator_context_manager_that_doesnt_suppress(
    pytester_dir: PytesterDir,
):
    run_and_assert_result(pytester_dir, failed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='start']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='0']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='end']")
    assert xml.xpath(
        "//kw[@name='Asdf' and ./status[@status='FAIL'] and ./msg[.='Exception']]"
    )
    assert not xml.xpath("//msg[.='1']")


def test_keyword_decorator_context_manager_that_raises_in_exit(
    pytester_dir: PytesterDir,
):
    run_and_assert_result(pytester_dir, failed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='start']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='0']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='FAIL' and .='asdf']")
    assert not xml.xpath("//msg[.='1']")


def test_keyword_decorator_context_manager_that_raises_in_body_and_exit(
    pytester_dir: PytesterDir,
):
    run_and_assert_result(
        pytester_dir, pytest_args=["--robotargs", "--loglevel DEBUG:INFO"], failed=1
    )
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='INFO' and .='start']")
    assert xml.xpath("//kw[@name='Asdf']/msg[@level='FAIL' and .='asdf']")
    assert xml.xpath(
        "//kw[@name='Asdf']/msg[@level='DEBUG' and contains(.,'Exception:"
        " fdsa\n\nDuring handling of the above exception, another exception"
        " occurred:') and contains(., 'Exception: asdf')]"
    )
    assert not xml.xpath("//msg[.='1']")


def test_keyword_decorator_try_except(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        "//kw[@name='Run Test' and ./status[@status='PASS']]/kw[@name='Bar' and"
        " ./status[@status='FAIL']]/msg[.='FooError']"
    )
    assert xml.xpath("//kw[@name='Run Test']/msg[.='hi']")


def test_keywordify_keyword_inside_context_manager(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        "//kw[@name='Raises' and ./arg[.=\"<class"
        " 'ZeroDivisionError'>\"]]/kw[@name='Asdf']"
    )


def test_keywordify_function(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, failed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath("//kw[@name='Fail' and ./arg[.='asdf']]")


def test_keywordify_context_manager(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        "//kw[@name='Raises' and ./arg[.=\"<class 'ZeroDivisionError'>\"] and"
        " ./status[@status='PASS']]"
    )


def test_tags(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(".//test[@name='test_tags']/tag[.='slow']")


def test_parameterized_tags(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(".//test[@name='test_tags']/tag[.='foo:bar']")


def test_keyword_names(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=2)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
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


def test_suite_variables(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)


def test_suite_variables_with_slash(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)


def test_variables_list(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)


def test_variables_not_in_scope_in_other_suites(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=2)
    assert_log_file_exists(pytester_dir)


def test_parametrize(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1, failed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath("//test[@name='test_eval[1-8]']")
    assert xml.xpath("//test[@name='test_eval[6-6]']")


def test_unittest_class(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)


def test_robot_keyword_in_python_test(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)


def test_xfail_fails(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, xfailed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        "//kw[@name='Run Test' and ./msg[@level='SKIP' and .='xfail: asdf']]"
    )


def test_xfail_passes(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, failed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        "//kw[@name='Run Test' and ./msg[@level='FAIL' and .='[XPASS(strict)] asdf']]"
    )


def test_xfail_fails_no_reason(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, xfailed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        "//kw[@name='Run Test' and ./msg[@level='SKIP' and .='xfail']]"
    )


def test_xfail_passes_no_reason(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, failed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        "//kw[@name='Run Test' and ./msg[@level='FAIL' and .='[XPASS(strict)] ']]"
    )


def test_listener_decorator(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)


def test_listener_decorator_registered_too_late(pytester_dir: PytesterDir):
    # not a top ledvel import due to https://github.com/DetachHead/pytest-robotframework/issues/38
    from pytest_robotframework._internal.errors import UserError

    result = pytester_dir.runpytest()
    result.assert_outcomes(errors=1)
    # pytest failed before test was collected so nothing in the robot run
    assert_robot_total_stats(pytester_dir)
    assert_log_file_exists(pytester_dir)
    assert (
        f"E   {UserError.__module__}.{UserError.__qualname__}: listener 'Listener'"
        " cannot be registered because robot has already started running. make sure"
        " it's defined in a `conftest.py` file"
        in result.outlines
    )


def test_catch_errors_decorator(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1, exit_code=ExitCode.INTERNAL_ERROR)
    assert_log_file_exists(pytester_dir)


def test_catch_errors_decorator_with_non_instance_method(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)


def test_no_tests_found_when_tests_exist(pytester_dir: PytesterDir):
    run_and_assert_result(
        pytester_dir, pytest_args=["asdfdsf"], exit_code=ExitCode.INTERNAL_ERROR
    )
    assert_log_file_exists(pytester_dir)


def test_assertion_fails(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, failed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath("//msg[@level='FAIL' and .='assert 1 == 2']")


def test_assertion_passes(pytester_dir: PytesterDir):
    run_and_assert_result(
        pytester_dir,
        pytest_args=[
            "-o",
            "enable_assertion_pass_hook=true",
            "--robotargs",
            "--loglevel DEBUG:INFO",
        ],
        subprocess=True,
        passed=1,
    )
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        "//kw[@name='assert' and ./arg['left == right']]/msg[@level='INFO' and"
        " .='1 == 1']"
    )


def test_assertion_pass_hook_multiple_tests(pytester_dir: PytesterDir):
    run_and_assert_result(
        pytester_dir,
        pytest_args=[
            "-o",
            "enable_assertion_pass_hook=true",
            "--robotargs",
            "--loglevel DEBUG:INFO",
        ],
        subprocess=True,
        passed=2,
    )
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        "//kw[@name='assert' and ./arg['left == right']]/msg[@level='INFO' and"
        " .='1 == 1']"
    )
    assert xml.xpath(
        "//kw[@name='assert' and ./arg['right == left']]/msg[@level='INFO' and"
        " .='1 == 1']"
    )


def test_keyword_and_pytest_raises(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        "//kw[@name='Raises']/kw[@name='Bar']/status[@status='FAIL']"
    )


def test_keyword_raises(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, failed=1)
    assert_log_file_exists(pytester_dir)
    assert output_xml(pytester_dir).xpath(
        "//kw[@name='Bar' and ./status[@status='FAIL'] and ./msg[.='FooError']]"
    )


def test_continue_on_failure_context_manager(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, failed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        "//kw[@name='Run Test']/kw[@name='continue_on_failure' and"
        " ./status[@status='FAIL'] and ./msg[.='ZeroDivisionError: division by zero']]"
    )
    assert xml.xpath("//kw[@name='Run Test']/msg[.='1']")
    assert xml.xpath(
        "//test[@name='test_foo']/status[.='failures that occurred inside a"
        " `continue_on_failure`:\n\n- division by zero\n\n']"
    )


def test_ignore_failure_context_manager(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        "//kw[@name='Run Test']/kw[@name='Ignore Failure' and"
        " ./status[@status='FAIL'] and ./msg[.='ZeroDivisionError: division by zero']]"
    )
    assert xml.xpath("//kw[@name='Run Test']/msg[.='1']")
    assert not xml.xpath(
        "//status[.='failures from"
        " keywords with `continue_on_failure` enabled:\n\n- division by zero\n\n']"
    )


def test_late_failures_and_normal_failure(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, failed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath(
        "//kw[@name='Run Test']/kw[@name='continue_on_failure' and"
        " ./status[@status='FAIL'] and ./msg[.='ZeroDivisionError: division by zero']]"
    )
    assert xml.xpath(
        "//test[@name='test_foo']/status[contains(., 'FooError') and contains(.,"
        " 'division by zero')]"
    )


def test_as_keyword_context_manager_passes(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath("//kw[@name='hi']/msg[.='1']")
    assert xml.xpath("//kw[@name='Run Test']/msg[.='2']")


def test_as_keyword_context_manager_continue_on_error(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, failed=1)
    assert_log_file_exists(pytester_dir)
    xml = output_xml(pytester_dir)
    assert xml.xpath("//kw[@name='hi' and ./status[@status='FAIL']]/msg[.='FooError']")
    assert xml.xpath("//kw[@name='Run Test']/msg[.='2']")


def test_invalid_fixture(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, errors=1, exit_code=ExitCode.TESTS_FAILED)
    assert_log_file_exists(pytester_dir)
    assert not output_xml(pytester_dir).xpath(
        "//*[contains(., 'Unknown exception type appeared')]"
    )


def test_pytest_runtest_protocol_session_hook(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)


def test_pytest_runtest_protocol_item_hook(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
