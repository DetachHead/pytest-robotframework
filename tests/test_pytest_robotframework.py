from __future__ import annotations

from typing import TYPE_CHECKING, cast

from lxml.etree import XML
from pytest import Pytester, mark

if TYPE_CHECKING:
    from lxml.etree import _Element


def output_xml(pytester: Pytester) -> _Element:
    return XML((pytester.path / "output.xml").read_bytes())


def get_robot_total_stats(pytester: Pytester) -> dict[str, str]:
    root = output_xml(pytester)
    statistics = next(child for child in root if child.tag == "statistics")
    total = next(child for child in statistics if child.tag == "total")
    return cast(
        dict[str, str],
        next(child for child in total if child.tag == "stat").attrib.__copy__(),
    )


def assert_log_file_exists(pytester: Pytester):
    assert (pytester.path / "log.html").exists()


def run_and_assert_result(
    pytester: Pytester, *, passed: int = 0, skipped: int = 0, failed: int = 0
):
    result = pytester.runpytest()
    result.assert_outcomes(passed=passed, skipped=skipped, failed=failed)
    assert get_robot_total_stats(pytester) == {
        "pass": str(passed),
        "fail": str(failed),
        "skip": str(skipped),
    }


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
        **{
            "test_one": """
                def test_func1():
                    pass
            """,
            "test_two": """
                def test_func2():
                    raise Exception("asdf")
            """,
        }
    )
    run_and_assert_result(pytester, passed=1, failed=1)
    assert_log_file_exists(pytester)


def test_two_tests_with_same_name_one_fail_one_pass(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        **{
            "test_one": """
                def test_func():
                    pass
            """,
            "test_two": """
                def test_func():
                    raise Exception("asdf")
            """,
        }
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


def test_doesnt_run_robot_files(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_func1():
            pass
        """
    )
    pytester.makefile(
        ".robot",
        """
        *** test cases ***
        foo
            should be true  ${False}
        """,
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)


def test_robot_args(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_func1():
            pass
        """
    )
    result = pytester.runpytest("--robotargs", "-d results")
    result.assert_outcomes(passed=1)
    assert (pytester.path / "results" / "log.html").exists()


def test_doesnt_run_when_collecting(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        def test_func1():
            pass
        """
    )
    result = pytester.runpytest("--collect-only")
    result.assert_outcomes()
    assert not (pytester.path / "log.html").exists()


def test_pytest_runtest_setup(pytester: Pytester):
    pytester.makepyfile(  # type:ignore[no-untyped-call]
        """
        from robot.api import logger

        def test_one_test_robot():
            logger.info(1)
        """
    )
    pytester.makeconftest(
        """
        from pytest import Item
        from robot.api import logger

        def pytest_runtest_setup(item: Item):
            logger.info(2)
        """
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)


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
