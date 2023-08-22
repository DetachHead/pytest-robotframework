from pytest import Mark, Pytester, Session

from tests.utils import (
    assert_log_file_exists,
    assert_robot_total_stats,
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


def test_one_test_skipped(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** test cases ***
        foo
            skip
        """,
    )
    run_and_assert_result(pytester, skipped=1)
    assert_log_file_exists(pytester)
    assert output_xml(pytester).xpath(
        "./suite//test[@name='foo']/kw/msg[@level='SKIP']"
    )


def test_two_tests_one_fail_one_pass(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** test cases ***
        foo
            log  1
        bar
            fail  2
        """,
    )
    run_and_assert_result(pytester, passed=1, failed=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath("./suite//test[@name='foo']//kw/msg[@level='INFO' and .='1']")
    assert xml.xpath("./suite//test[@name='bar']//kw/msg[@level='FAIL' and .='2']")


def test_setup_passes(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** settings ***
        test setup  bar
        *** test cases ***
        foo
            log  1
        *** keywords ***
        bar
            log  2
        """,
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)
    assert output_xml(pytester).xpath(
        "./suite//test[@name='foo']/kw[@type='SETUP']/kw[@name='bar']/kw[@name='Log']/arg[.='2']"
    )


def test_setup_fails(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** settings ***
        test setup  bar
        *** test cases ***
        foo
            log  1
        *** keywords ***
        bar
            fail  asdf
        """,
    )
    run_and_assert_result(pytester, errors=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(
        "//suite//test[@name='foo']/kw[@type='SETUP']/kw[@name='bar' and .//msg[@level='FAIL' and .='asdf'] and .//status[@status='FAIL']]"
    )
    # make sure the test didnt run when setup failed
    assert not xml.xpath("//kw[contains(@name, 'Run Test')]")


def test_setup_skipped(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** settings ***
        test setup  bar
        *** test cases ***
        foo
            log  1
        *** keywords ***
        bar
            skip
        """,
    )
    run_and_assert_result(pytester, skipped=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(
        "//suite//test[@name='foo']/kw[@type='SETUP']/kw[@name='bar' and .//msg[@level='SKIP']]"
    )
    # make sure the test didnt run when setup was skipped
    assert not xml.xpath("//kw[contains(@name, 'Run Test')]")


def test_teardown_passes(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** settings ***
        test teardown  bar
        *** test cases ***
        foo
            log  1
        *** keywords ***
        bar
            log  2
        """,
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)
    assert output_xml(pytester).xpath(
        "./suite//test[@name='foo']/kw[@type='TEARDOWN']/kw[@name='bar']/kw[@name='Log']/arg[.='2']"
    )


def test_teardown_fails(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** settings ***
        test teardown  bar
        *** test cases ***
        foo
            log  1
        *** keywords ***
        bar
            fail  asdf
        """,
    )
    result = run_pytest(pytester)
    result.assert_outcomes(passed=1, errors=1)
    # unlike pytest, teardown failures in robot count as a test failure
    assert_robot_total_stats(pytester, failed=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(
        "//suite//test[@name='foo']/kw[@type='TEARDOWN']/kw[@name='bar' and .//msg[@level='FAIL' and .='asdf'] and .//status[@status='FAIL']]"
    )
    assert xml.xpath("//kw[contains(@name, 'Run Test')]")


def test_teardown_skipped(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** settings ***
        test teardown  bar
        *** test cases ***
        foo
            log  1
        *** keywords ***
        bar
            skip
        """,
    )
    result = run_pytest(pytester)
    result.assert_outcomes(passed=1, skipped=1)
    # unlike pytest, teardown skips in robot count as a test skip
    assert_robot_total_stats(pytester, skipped=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(
        "//suite//test[@name='foo']/kw[@type='TEARDOWN']/kw[@name='bar' and .//msg[@level='SKIP']]"
    )
    assert xml.xpath("//kw[contains(@name, 'Run Test')]")


def test_two_files_run_one_test(pytester: Pytester):
    pytester.makefile(
        ".robot",
        **{
            "foo.robot": """
                *** test cases ***
                foo
                    log  1
                bar
                    log  1
            """,
            "bar.robot": """
                *** test cases ***
                baz
                    log  1
            """,
        },
    )
    run_and_assert_result(pytester, pytest_args=["foo.robot::foo"], passed=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath("./suite//test[@name='foo']/status[@status='PASS']")
    assert xml.xpath("./suite//test[@name='foo']/kw/status[@status='PASS']")
    assert not xml.xpath("./suite//test[@name='bar']")
    assert not xml.xpath("./suite//test[@name='baz']")


def test_two_files_run_test_from_second_suite(pytester: Pytester):
    """makes sure `CollectedTestsFilterer` correctly filters the tests without
    mutating the list of tests as it iterates ver it"""
    pytester.makefile(
        ".robot",
        **{
            "asdf/foo.robot": """
                *** test cases ***
                foo
                    log  1
                bar
                    log  1
            """,
            "fdsa/bar.robot": """
                *** test cases ***
                baz
                    log  1
            """,
        },
    )
    run_and_assert_result(pytester, pytest_args=["fdsa/bar.robot::baz"], passed=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath("./suite//test[@name='baz']/status[@status='PASS']")
    assert xml.xpath("./suite//test[@name='baz']/kw/status[@status='PASS']")
    assert not xml.xpath("./suite//test[@name='foo']")
    assert not xml.xpath("./suite//test[@name='bar']")


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


def test_tags_in_settings(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** settings ***
        test tags  m1
        *** test cases ***
        foo
            no operation
        bar
            no operation
        """,
    )
    run_and_assert_result(pytester, pytest_args=["-m", "m1"], passed=2)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(".//test[@name='foo']/tag[.='m1']")
    assert xml.xpath(".//test[@name='bar']/tag[.='m1']")


def test_warning_on_unknown_tag(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** test cases ***
        foo
            [tags]  m1
            no operation
        """,
    )
    # TODO: figure out why the error message is wack
    #  https://github.com/DetachHead/pytest-robotframework/issues/37
    result = run_pytest(pytester, "--strict-markers", "-m", "m1")
    result.assert_outcomes(errors=1)


def test_parameterized_tags(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** test cases ***
        foo
            [tags]  key:hi
            no operation
        """,
    )
    pytester.makeini(
        """
        [pytest]
        markers =
            key(value)
        """
    )
    markers: list[Mark] | None = None

    class TagGetter:
        @staticmethod
        def pytest_collection_finish(session: Session):
            nonlocal markers
            for item in session.items:
                markers = item.own_markers

    run_pytest(pytester, "--collectonly", "--strict-markers", plugins=[TagGetter()])
    assert markers
    assert len(markers) == 1
    assert markers[0].name == "key"
    assert markers[0].args == ("hi",)  # type:ignore[no-any-expr]


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


def test_doesnt_run_tests_outside_path(pytester: Pytester):
    pytester.makefile(
        ".robot",
        **{
            "foo/asdf.robot": """
                *** test cases ***
                foo
                    log  1
            """,
            "bar/asdf.robot": """
                *** test cases ***
                bar
                    log  1
            """,
        },
    )
    run_and_assert_result(pytester, pytest_args=["foo"], passed=1)
    assert_log_file_exists(pytester)
    xml = output_xml(pytester)
    assert xml.xpath(".//test[@name='foo']")
    assert not xml.xpath(".//test[@name='bar']")


def test_run_keyword_and_ignore_error(pytester: Pytester):
    pytester.makefile(
        ".py",
        foo="""
            from pytest_robotframework import keyword
                            
            @keyword
            def bar():
                raise Exception
        """,
    )
    make_robot_file(
        pytester,
        """
        library  foo
        *** test cases ***
        foo
            run keyword and ignore error  bar
        """,
    )
    run_and_assert_result(pytester, passed=1)
    assert_log_file_exists(pytester)


def test_init_file(pytester: Pytester):
    make_robot_file(
        pytester,
        """
        *** test cases ***
        foo
            no operation
        """,
    )
    pytester.makefile(".py", __init__="")
    result = run_pytest(pytester)
    result.assert_outcomes(passed=1)
    assert (pytester.path / "log.html").exists()
