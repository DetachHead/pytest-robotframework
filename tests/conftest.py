from __future__ import annotations

from copy import copy as copy_object
from os import PathLike, symlink
from pathlib import Path
from shutil import copy, copytree
from types import ModuleType
from typing import TYPE_CHECKING, Literal, cast, overload

from lxml.etree import XML
from pytest import ExitCode, FixtureRequest, Function, Pytester, RunResult, fixture

if TYPE_CHECKING:
    from _typeshed import StrPath
    from lxml.etree import _Element  # pyright:ignore[reportPrivateUsage]
    from typing_extensions import Never, override

# needed for fixtures that depend on other fixtures
# pylint:disable=redefined-outer-name

pytest_plugins = ["pytester"]


def try_symlink(src: StrPath, dest: StrPath):
    """try to use symlinks so breakpoints in the copied python files still work

    but some computers don't support symlinks so fall back to the copy method"""
    try:
        symlink(src, dest)
    except OSError:
        copy(src, dest)


@fixture
def pytester_dir(pytester: Pytester, request: FixtureRequest) -> PytesterDir:
    """wrapper for pytester that moves the files located in
    `tests/fixtures/[test file]/[test name].py` to the pytester temp dir for the current test, so
    you don't have to write your test files as strings with the `makefile`/`makepyfile` methods
    """
    test = cast(Function, request.node)  # pyright:ignore[reportUnknownMemberType]
    test_name = test.originalname
    fixtures_folder = Path(__file__).parent / "fixtures"
    test_file_fixture_dir = (
        fixtures_folder
        / Path(cast(str, cast(ModuleType, test.module).__file__))
        .relative_to(Path(__file__).parent)
        .stem
    )
    fixture_dir_for_current_test = test_file_fixture_dir / test_name
    if fixture_dir_for_current_test.exists():
        copytree(
            fixture_dir_for_current_test,
            pytester.path,
            dirs_exist_ok=True,
            copy_function=try_symlink,
        )
    elif test_file_fixture_dir.exists():
        for file in (
            test_file_fixture_dir / f"{test_name}.{ext}" for ext in ("py", "robot")
        ):
            if file.exists():
                try_symlink(file, pytester.path / file.name)
                break
        else:
            raise Exception(f"no fixtures found for {test_name=}")
    return cast(PytesterDir, pytester)


if TYPE_CHECKING:
    # Pytester is final so it's probably a bad idea to rely on extending this at runtime
    # https://github.com/DetachHead/basedpyright/issues/23
    class PytesterDir(Pytester):  # pyright:ignore # noqa: PGH003
        """fake subtype of `Pytester` that bans you from using file creation and runpytest methods.
        you should put real life files in `tests/fixtures/[test file path]/[test name]` instead,
        and use the runpytest methods on `PytestRobotTester` since they have handling for the xdist
        parameterization"""

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

        @override
        def runpytest(self, *args: str | PathLike[str], **kwargs: Never) -> Never: ...

        @override
        def runpytest_inprocess(
            self, *args: str | PathLike[str], **kwargs: Never
        ) -> Never: ...

        @override
        def runpytest_subprocess(
            self, *args: str | PathLike[str], timeout: float | None = None
        ) -> Never: ...

else:
    PytesterDir = Pytester


@fixture(params=[True, False], ids=["xdist_on", "xdist_off"])
def pr(pytester_dir: PytesterDir, request: FixtureRequest) -> PytestRobotTester:
    return PytestRobotTester(pytester=pytester_dir, xdist=request.param)


class PytestRobotTester:
    def __init__(self, *, pytester: PytesterDir, xdist: bool):
        super().__init__()
        self.pytester = pytester
        self.xdist: bool = xdist
        self.xdist_count = 2

    def output_xml(self) -> _Element:
        return XML((self.pytester.path / "output.xml").read_bytes())

    def assert_robot_total_stats(
        self, *, passed: int = 0, skipped: int = 0, failed: int = 0
    ):
        root = self.output_xml()
        statistics = next(child for child in root if child.tag == "statistics")
        total = next(child for child in statistics if child.tag == "total")
        result = copy_object(
            next(child for child in total if child.tag == "stat").attrib
        )
        assert result == {
            "pass": str(passed),
            "fail": str(failed),
            "skip": str(skipped),
        }

    def _log_file_exists(self):
        return (self.pytester.path / "log.html").exists()

    def assert_log_file_exists(self, *, check_xdist: bool = True):
        """asserts that robot generated a log file, and ensures that it did/didn't use xdist.

        set `check_xdist` to `False` if you expect no tests to have been run (in which case most
        of the xdist-specific logic won't get hit so the xdist check would fail)"""
        assert self._log_file_exists()
        # far from perfect but we can be reasonably confident that the xdist stuff ran if this
        # folder exists
        if check_xdist or not self.xdist:
            assert self.xdist == bool(
                list(self.pytester.path.glob("**/robot_xdist_outputs"))
            )

    def assert_log_file_doesnt_exist(self):
        assert not self._log_file_exists()

    def run_and_assert_assert_pytest_result(
        self,
        *,
        pytest_args: list[str] | None = None,
        subprocess: bool = True,
        passed: int = 0,
        skipped: int = 0,
        failed: int = 0,
        errors: int = 0,
        xfailed: int = 0,
        exit_code: ExitCode | None = None,
    ):
        result = self.run_pytest(*pytest_args or [], subprocess=subprocess)

        if not exit_code:
            if errors:
                exit_code = ExitCode.INTERNAL_ERROR
            elif failed:
                exit_code = ExitCode.TESTS_FAILED
            else:
                exit_code = ExitCode.OK
        if exit_code == ExitCode.USAGE_ERROR:
            # i dont think results are always generated if theres a pytest usage error
            if passed or skipped or failed or errors or xfailed:
                raise Exception(
                    "cannot specify expected pytest outcomes when expected exit code is"
                    " USAGE_ERROR"
                )
        else:
            result.assert_outcomes(
                passed=passed,
                skipped=skipped,
                failed=failed,
                errors=errors,
                xfailed=xfailed,
            )
        try:
            assert result.ret == exit_code
        except AssertionError:
            if self.xdist:
                # workaround for https://github.com/pytest-dev/pytest-xdist/issues/1017
                assert (exit_code != ExitCode.OK) == any(
                    line
                    for line in result.outlines
                    if line.startswith("INTERNALERROR>")
                )
            else:
                raise

    @overload
    def run_pytest(
        self,
        *args: str,
        subprocess: Literal[False],
        plugins: list[object] | None = None,
    ) -> RunResult: ...

    @overload
    def run_pytest(self, *args: str, subprocess: bool = ...) -> RunResult: ...

    def run_pytest(
        self, *args: str, subprocess: bool = True, plugins: list[object] | None = None
    ) -> RunResult:
        if self.xdist:
            args += ("-n", str(self.xdist_count))
        pytester = cast(Pytester, self.pytester)
        return (
            pytester.runpytest_subprocess(*args)
            if subprocess
            else pytester.runpytest(*args, plugins=plugins or [])
        )

    def run_and_assert_result(
        self,
        *,
        pytest_args: list[str] | None = None,
        subprocess: bool = True,
        passed: int = 0,
        skipped: int = 0,
        failed: int = 0,
        errors: int = 0,
        xfailed: int = 0,
        exit_code: ExitCode | None = None,
    ):
        if pytest_args is None:
            pytest_args = []
        self.run_and_assert_assert_pytest_result(
            pytest_args=pytest_args,
            subprocess=subprocess,
            passed=passed,
            skipped=skipped,
            failed=failed,
            errors=errors,
            xfailed=xfailed,
            exit_code=exit_code,
        )
        self.assert_robot_total_stats(
            passed=passed,
            # most things that are errors in pytest are failures in robot. also robot doesn't store
            #  errors here
            # TODO: a way to check for robot errors, i think they currently go undetected
            #  https://github.com/DetachHead/pytest-robotframework/issues/39
            failed=failed + errors,
            # robot doesn't have xfail, uses skips instead
            skipped=skipped + xfailed,
        )
