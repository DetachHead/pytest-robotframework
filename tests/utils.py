from __future__ import annotations

from typing import TYPE_CHECKING, Never, cast

from lxml.etree import XML
from pytest import Pytester, RunResult

if TYPE_CHECKING:
    from lxml.etree import _Element
    from typing_extensions import override


if TYPE_CHECKING:
    # Pytester is final so it's probably a bad idea to rely on extending this at runtime
    class PytesterDir(Pytester):  # type:ignore[misc]
        """fake subtype of `Pytester` that bans you from using file creation methods. you should put
        real life files in `tests/fixtures/[test file path]/[test name]` instead"""

        @override
        def makepyfile(self, *args: Never, **kwargs: Never) -> Never:
            ...

        @override
        def makefile(self, ext: str, *args: str, **kwargs: str) -> Never:
            ...

        @override
        def makeini(self, source: str) -> Never:
            ...

        @override
        def makepyprojecttoml(self, source: str) -> Never:
            ...

        @override
        def maketxtfile(self, *args: Never, **kwargs: Never) -> Never:
            ...

else:
    PytesterDir = Pytester


def output_xml(pytester: PytesterDir) -> _Element:
    return XML((pytester.path / "output.xml").read_bytes())


def assert_robot_total_stats(pytester: PytesterDir, *, passed=0, skipped=0, failed=0):
    root = output_xml(pytester)
    statistics = next(child for child in root if child.tag == "statistics")
    total = next(child for child in statistics if child.tag == "total")
    result = cast(
        dict[str, str],
        next(child for child in total if child.tag == "stat").attrib.__copy__(),
    )
    assert result == {"pass": str(passed), "fail": str(failed), "skip": str(skipped)}


def assert_log_file_exists(pytester: Pytester):
    assert (pytester.path / "log.html").exists()


def run_pytest(
    pytester: PytesterDir, *pytest_args: str, plugins: list[object] | None = None
) -> RunResult:
    # TODO: figure out why robot doesn't use pytester's cd anymore. started happening when
    #  i added a test that calls a function from the plugin directly instead of using pytester
    #  https://github.com/DetachHead/pytest-robotframework/issues/38
    return pytester.runpytest(
        *pytest_args, "--robotargs", f"-d {pytester.path}", plugins=plugins or []
    )


def run_and_assert_result(
    pytester: PytesterDir,
    *,
    pytest_args: list[str] | None = None,
    passed=0,
    skipped=0,
    failed=0,
    errors=0,
    xfailed=0,
):
    result = run_pytest(pytester, *(pytest_args or []))
    result.assert_outcomes(
        passed=passed, skipped=skipped, failed=failed, errors=errors, xfailed=xfailed
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
