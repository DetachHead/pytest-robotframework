from __future__ import annotations

from typing import TYPE_CHECKING, cast

from lxml.etree import XML

if TYPE_CHECKING:
    from lxml.etree import _Element
    from pytest import Pytester, RunResult


def output_xml(pytester: Pytester) -> _Element:
    return XML((pytester.path / "output.xml").read_bytes())


def assert_robot_total_stats(pytester: Pytester, *, passed=0, skipped=0, failed=0):
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
    pytester: Pytester, *pytest_args: str, plugins: list[object] | None = None
) -> RunResult:
    # TODO: figure out why robot doesn't use pytester's cd anymore. started happening when
    #  i added a test that calls a function from the plugin directly instead of using pytester
    #  https://github.com/DetachHead/pytest-robotframework/issues/38
    return pytester.runpytest(
        *pytest_args, "--robotargs", f"-d {pytester.path}", plugins=plugins or []
    )


def run_and_assert_result(
    pytester: Pytester,
    *,
    pytest_args: list[str] | None = None,
    passed=0,
    skipped=0,
    failed=0,
    errors=0,
):
    result = run_pytest(pytester, *(pytest_args or []))
    result.assert_outcomes(passed=passed, skipped=skipped, failed=failed, errors=errors)
    assert_robot_total_stats(
        pytester,
        passed=passed,
        # most things that are errors in pytest are failures in robot. also robot doesn't store errors here
        # TODO: a way to check for robot errors, i think they currently go undetected
        #  https://github.com/DetachHead/pytest-robotframework/issues/39
        failed=failed + errors,
        skipped=skipped,
    )
