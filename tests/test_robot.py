from pytest import Mark, Pytester, Session

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
        def pytest_collection_finish(self, session: Session):
            nonlocal markers
            for item in session.items:
                markers = item.own_markers

    run_pytest(pytester, "--collectonly", "--strict-markers", plugins=[TagGetter()])
    assert markers and len(markers) == 1
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
