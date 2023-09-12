from __future__ import annotations

from typing import TYPE_CHECKING, Dict, cast

from lxml.etree import XML
from pytest import ExitCode, Pytester

if TYPE_CHECKING:
    from lxml.etree import _Element
    from typing_extensions import Never, override


if TYPE_CHECKING:
    # Pytester is final so it's probably a bad idea to rely on extending this at runtime
    class PytesterDir(Pytester):  # type:ignore[misc]
        """fake subtype of `Pytester` that bans you from using file creation methods. you should put
        real life files in `tests/fixtures/[test file path]/[test name]` instead"""

        @override
        def makepyfile(self, *args: Never, **kwargs: Never) -> Never: ...

        @override
        def makefile(self, ext: str, *args: str, **kwargs: str) -> Never: ...

        @override
        def makeini(self, source: str) -> Never: ...

        @override
        def makepyprojecttoml(self, source: str) -> Never: ...

        @override
        def maketxtfile(self, *args: Never, **kwargs: Never) -> Never: ...

else:
    PytesterDir = Pytester


def output_xml(pytester: Pytester) -> _Element:
    return XML((pytester.path / "output.xml").read_bytes())


def assert_robot_total_stats(pytester: Pytester, *, passed=0, skipped=0, failed=0):
    root = output_xml(pytester)
    statistics = next(child for child in root if child.tag == "statistics")
    total = next(child for child in statistics if child.tag == "total")
    result = cast(
        Dict[str, str],
        next(child for child in total if child.tag == "stat").attrib.__copy__(),
    )
    assert result == {"pass": str(passed), "fail": str(failed), "skip": str(skipped)}


def assert_log_file_exists(pytester: Pytester):
    assert (pytester.path / "log.html").exists()


def run_and_assert_assert_pytest_result(
    pytester: Pytester,
    *,
    pytest_args: list[str] | None = None,
    subprocess=False,
    passed=0,
    skipped=0,
    failed=0,
    errors=0,
    xfailed=0,
    exit_code: ExitCode | None = None,
):
    result = (
        pytester.runpytest_subprocess
        if subprocess
        else pytester.runpytest  # type:ignore[no-any-expr]
    )(*(pytest_args or []))
    result.assert_outcomes(
        passed=passed, skipped=skipped, failed=failed, errors=errors, xfailed=xfailed
    )
    if not exit_code:
        if errors:
            exit_code = ExitCode.INTERNAL_ERROR
        elif failed:
            exit_code = ExitCode.TESTS_FAILED
        else:
            exit_code = ExitCode.OK
    assert result.ret == exit_code


def run_and_assert_result(
    pytester: Pytester,
    *,
    pytest_args: list[str] | None = None,
    subprocess=False,
    passed=0,
    skipped=0,
    failed=0,
    errors=0,
    xfailed=0,
    exit_code: ExitCode | None = None,
):
    run_and_assert_assert_pytest_result(
        pytester,
        pytest_args=pytest_args,
        subprocess=subprocess,
        passed=passed,
        skipped=skipped,
        failed=failed,
        errors=errors,
        xfailed=xfailed,
        exit_code=exit_code,
    )
    assert_robot_total_stats(
        pytester,
        passed=passed,
        # most things that are errors in pytest are failures in robot. also robot doesn't store
        #  errors here
        # TODO: a way to check for robot errors, i think they currently go undetected
        #  https://github.com/DetachHead/pytest-robotframework/issues/39
        failed=failed + errors,
        # robot doesn't have xfail, uses skips instead
        skipped=skipped + xfailed,
    )
