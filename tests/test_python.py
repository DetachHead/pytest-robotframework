from __future__ import annotations

import os

from pytest import Pytester, mark

from tests.utils import (
    assert_log_file_exists,
    assert_robot_total_stats,
    output_xml,
    run_and_assert_result,
    run_pytest,
)


def test_one_test_passes(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_one_test_robot():
            pass
        """
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)


def test_one_test_fails(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_one_test_robot():
            raise Exception("asdf")
        """
    )
    run_and_assert_result(pytester, failed=1)
    assert_log_file_exists(pytester)


def test_one_test_skipped(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        from pytest import mark

        @mark.skipif(True, reason="foo")
        def test_one_test_skipped():
            raise Exception("asdf")
        """
    )
    run_and_assert_result(pytester, skipped=1)
    assert_log_file_exists(pytester)
    assert output_xml(pytester).xpath(
        "./suite//test[@name='test_one_test_skipped']/kw[@type='SETUP']/msg[@level='SKIP']"
    )


def test_two_tests_one_fail_one_pass(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_one():
            pass

        def test_two():
            raise Exception("asdf")
        """
    )
    run_and_assert_result(pytester, passed=1, failed=1)
    assert_log_file_exists(pytester)


def test_two_tests_two_files_one_fail_one_pass(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        test_one="""
            def test_func1():
                pass
        """,
        test_two="""
            def test_func2():
                raise Exception("asdf")
        """,
    )
    run_and_assert_result(pytester, passed=1, failed=1)
    assert_log_file_exists(pytester)


def test_two_tests_with_same_name_one_fail_one_pass(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        test_one="""
                def test_func():
                    pass
            """,
        test_two="""
                def test_func():
                    raise Exception("asdf")
            """,
    )
    run_and_assert_result(pytester, passed=1, failed=1)
    assert_log_file_exists(pytester)


def test_suites(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        **{
            "suite1/test_asdf": """
                def test_func1():
                    pass
            """
        }
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)
    assert output_xml(pytester).xpath(
        "./suite/suite[@name='Suite1']/suite[@name='Test Asdf']/test[@name='test_func1']"
    )


def test_nested_suites(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        **{
            "suite1/suite2/test_asdf": """
                def test_func1():
                    pass
            """,
            "suite1/suite3/test_asdf2": """
                def test_func2():
                    pass
            """,
            "test_top_level": """
                def test_func1():
                    raise Exception("asdf")
            """,
        }
    )
    run_and_assert_result(pytester, passed=2, failed=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(
        "./suite/suite[@name='Suite1']/suite[@name='Suite2']/suite[@name='Test Asdf']/test[@name='test_func1']"
    )
    assert xml.xpath(
        "./suite/suite[@name='Suite1']/suite[@name='Suite3']/suite[@name='Test Asdf2']/test[@name='test_func2']"
    )
    assert xml.xpath("./suite/suite[@name='Test Top Level']/test[@name='test_func1']")


def test_robot_args(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_func1():
            pass
        """
    )
    results_path = pytester.path / "results"
    result = pytester.runpytest("--robotargs", f"-d {results_path}")
    result.assert_outcomes(passed=1)
    assert (results_path / "log.html").exists()


def test_robot_options_variable(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_func1():
            pass
        """
    )
    results_path = pytester.path / "results"
    env_variable = "ROBOT_OPTIONS"
    try:
        os.environ[env_variable] = f"-d {results_path}"
        result = pytester.runpytest()
    finally:
        del os.environ[env_variable]
    result.assert_outcomes(passed=1)
    assert (results_path / "log.html").exists()


def test_robot_options_merge_listeners(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        Listener="""
            from robot import result, running
            from robot.api.interfaces import ListenerV3
            from typing_extensions import override
            
            called = False
            class Listener(ListenerV3):
                @override
                def start_suite(self, data: running.TestSuite, result: result.TestSuite):
                    global called
                    called = True
        """
    )
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        test_foo="""
            import Listener
            def test_func1():
                assert Listener.called
        """
    )
    result = pytester.runpytest(
        "--robotargs", f"--listener {pytester.path / 'Listener.py'}"
    )
    result.assert_outcomes(passed=1)
    assert_log_file_exists(pytester)


def test_robot_options_variable_merge_listeners(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        Listener="""
            from robot import result, running
            from robot.api.interfaces import ListenerV3
            from typing_extensions import override
            
            called = False
            class Listener(ListenerV3):
                @override
                def start_suite(self, data: running.TestSuite, result: result.TestSuite):
                    global called
                    called = True
        """
    )
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        test_foo="""
            import Listener
            def test_func1():
                assert Listener.called
        """
    )
    env_variable = "ROBOT_OPTIONS"
    try:
        os.environ[env_variable] = f"--listener {pytester.path / 'Listener.py'}"
        result = pytester.runpytest()
    finally:
        del os.environ[env_variable]
    result.assert_outcomes(passed=1)
    assert_log_file_exists(pytester)


def test_doesnt_run_when_collecting(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_func1():
            pass
        """
    )
    result = run_pytest(pytester, "--collect-only")
    result.assert_outcomes()
    assert not (pytester.path / "log.html").exists()


def test_setup_passes(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        from robot.api import logger

        def test_one_test_robot():
            logger.info(1)
        """
    )
    pytester.makeconftest(
        """
        from robot.api import logger

        def pytest_runtest_setup():
            logger.info(2)
        """
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(
        ".//test/kw[contains(@name, ' Setup')]/msg[@level='INFO' and .='2']"
    )
    assert xml.xpath(
        ".//test/kw[contains(@name, ' Run Test')]/msg[@level='INFO' and .='1']"
    )


def test_setup_fails(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_one_test_robot():
            pass
        """
    )
    pytester.makeconftest(
        """
        def pytest_runtest_setup():
            raise Exception('2')
        """
    )
    run_and_assert_result(pytester, errors=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(
        ".//test/kw[contains(@name, ' Setup')]/msg[@level='FAIL' and .='Exception: 2']"
    )
    assert not xml.xpath(".//test/kw[contains(@name, ' Run Test')]")


def test_setup_skipped(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_one_test_robot():
            pass
        """
    )
    pytester.makeconftest(
        """
        from pytest import skip
        
        def pytest_runtest_setup():
            skip()
        """
    )
    run_and_assert_result(pytester, skipped=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(".//test/kw[contains(@name, ' Setup')]/msg[@level='SKIP']")
    assert not xml.xpath(".//test/kw[contains(@name, ' Run Test')]")


def test_teardown_passes(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        from robot.api import logger

        def test_one_test_robot():
            logger.info(1)
        """
    )
    pytester.makeconftest(
        """
        from robot.api import logger

        def pytest_runtest_teardown():
            logger.info(2)
        """
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(
        ".//test/kw[contains(@name, ' Run Test')]/msg[@level='INFO' and .='1']"
    )
    assert xml.xpath(
        ".//test/kw[contains(@name, ' Teardown')]/msg[@level='INFO' and .='2']"
    )


def test_teardown_fails(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_one_test_robot():
            pass
        """
    )
    pytester.makeconftest(
        """
        def pytest_runtest_teardown():
            raise Exception('2')
        """
    )
    result = run_pytest(pytester)
    result.assert_outcomes(passed=1, errors=1)
    # unlike pytest, teardown failures in robot count as a test failure
    assert_robot_total_stats(pytester, failed=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(".//test/kw[contains(@name, ' Run Test')]")
    assert xml.xpath(
        ".//test/kw[contains(@name, ' Teardown')]/msg[@level='FAIL' and .='Exception: 2']"
    )


def test_teardown_skipped(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_one_test_robot():
            pass
        """
    )
    pytester.makeconftest(
        """
        from pytest import skip
        
        def pytest_runtest_teardown():
            skip()
        """
    )
    result = run_pytest(pytester)
    result.assert_outcomes(passed=1, skipped=1)
    # unlike pytest, teardown skips in robot count as a test skip
    assert_robot_total_stats(pytester, skipped=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(".//test/kw[contains(@name, ' Run Test')]")
    assert xml.xpath(".//test/kw[contains(@name, ' Teardown')]/msg[@level='SKIP']")


def test_fixture(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        from pytest import CaptureFixture

        def test_fixture(capfd: CaptureFixture):
            assert isinstance(capfd, CaptureFixture)
        """
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)


def test_module_docstring(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        \"\"\"hello???\"\"\"
        def test_nothing():
            ...
        """
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)
    assert output_xml(pytester).xpath("./suite/suite/doc[.='hello???']")


def test_test_case_docstring(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_docstring():
            \"\"\"hello???\"\"\"
        """
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)
    assert output_xml(pytester).xpath("./suite/suite/test/doc[.='hello???']")


def test_keyword_decorator(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        from pytest_robotframework import keyword

        @keyword
        def foo():
            \"\"\"hie\"\"\"

        def test_docstring():
            foo()
        """
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)
    assert output_xml(pytester).xpath(
        ".//kw[contains(@name, ' Run Test')]/kw[@name='foo']/doc[.='hie']"
    )


def test_tags(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        from pytest import mark

        @mark.slow
        def test_tags():
            ...
        """
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(".//test[@name='test_tags']/tag[.='slow']")


def test_parameterized_tags(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        from pytest import mark

        @mark.foo("bar")
        def test_tags():
            ...
        """
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(".//test[@name='test_tags']/tag[.='foo:bar']")


@mark.xfail(
    reason="TODO: figure out how to modify the keyword names before the xml is written or read the html file instead"
)
def test_keyword_names(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_0():
            pass
        def test_1():
            pass
        """
    )
    run_and_assert_result(pytester, passed=2)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    for index in range(2):
        assert xml.xpath(f".//test[@name='test_{index}']/kw[@name='Setup']")
        assert xml.xpath(f".//test[@name='test_{index}']/kw[@name='Run Test']")
        assert xml.xpath(f".//test[@name='test_{index}']/kw[@name='Teardown']")


def test_suite_variables(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        from pytest_robotframework import set_variables
        from robot.libraries.BuiltIn import BuiltIn

        set_variables({"foo":{"bar": ""}})

        def test_asdf():
            assert BuiltIn().get_variable_value("$foo") == {"bar": ""}
        """
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)


def test_variables_list(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        from pytest_robotframework import set_variables
        from robot.libraries.BuiltIn import BuiltIn

        set_variables({"foo": ["bar", "baz"]})

        def test_asdf():
            assert BuiltIn().get_variable_value("$foo") == ["bar", "baz"]
        """
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)


def test_variables_not_in_scope_in_other_suites(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        test_one="""
            from pytest_robotframework import set_variables
            from robot.libraries.BuiltIn import BuiltIn

            set_variables({"foo": "bar"})

            def test_asdf():
                assert BuiltIn().get_variable_value("$foo") == "bar"
        """,
        test_two="""
            from robot.libraries.BuiltIn import BuiltIn

            def test_func():
                assert BuiltIn().get_variable_value("$foo") is None
        """,
    )
    run_and_assert_result(pytester, passed=2)
    assert_log_file_exists(pytester)


def test_parameterize(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        from pytest import mark

        @mark.parametrize("test_input,expected", [(1, 8), (6, 6)])
        def test_eval(test_input: int, expected: int):
            assert test_input == expected
        """
    )
    run_and_assert_result(pytester, passed=1, failed=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath("//test[@name='test_eval[1-8]']")
    assert xml.xpath("//test[@name='test_eval[6-6]']")


def test_unittest_class(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        from unittest import TestCase

        class TestSet(TestCase):
            def test_foo(self):
                ...
        """
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)


def test_robot_keyword_in_python_test(pytester: Pytester):
    pytester.makefile(
        ".resource",
        bar="""
            *** keywords ***
            bar
                log  1
        """,
    )
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        from pytest_robotframework import import_resource
        from robot.libraries.BuiltIn import BuiltIn

        import_resource("bar.resource")

        def test_foo():
            BuiltIn().run_keyword('bar')
        """
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)
