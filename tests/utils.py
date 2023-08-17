from __future__ import annotations

from typing import TYPE_CHECKING, cast

from lxml.etree import XML
from pytest import Pytester, RunResult

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


def run_pytest(
    pytester: Pytester, *pytest_args: str, plugins: list[object] | None = None
) -> RunResult:
    # TODO: figure out why robot doesn't use pytester's cd anymore. started happening when
    #  i added a test that calls a function from the plugin directly instead of using pytester
    return pytester.runpytest(
        *pytest_args, "--robotargs", f"-d {pytester.path}", plugins=plugins or []
    )


def run_and_assert_result(
    pytester: Pytester,
    *,
    pytest_args: list[str] | None = None,
    passed: int = 0,
    skipped: int = 0,
    failed: int = 0,
):
    result = run_pytest(pytester, *(pytest_args or []))
    result.assert_outcomes(passed=passed, skipped=skipped, failed=failed)
    assert get_robot_total_stats(pytester) == {
        "pass": str(passed),
        "fail": str(failed),
        "skip": str(skipped),
    }
