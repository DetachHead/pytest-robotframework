from __future__ import annotations

from collections.abc import Iterable, Iterator
from copy import copy as copy_object
from os import PathLike, symlink
from pathlib import Path
from shutil import copy, copytree
from types import ModuleType
from typing import TYPE_CHECKING, Literal, cast, final, overload

from lxml.etree import (
    XML,
    _Element,  # pyright: ignore[reportPrivateUsage]
)
from pytest import ExitCode, FixtureRequest, Function, Pytester, RunResult, fixture
from typing_extensions import TypeGuard, override

if TYPE_CHECKING:
    from _typeshed import StrPath
    from lxml.etree import (
        _AnyStr,  # pyright: ignore[reportPrivateUsage]
        _NonDefaultNSMapArg,  # pyright: ignore[reportPrivateUsage]
        _XPathObject,  # pyright: ignore[reportPrivateUsage]
    )
    from typing_extensions import Never

# needed for fixtures that depend on other fixtures
# pylint:disable=redefined-outer-name

pytest_plugins = ["pytester"]


def try_symlink(src: StrPath, dest: StrPath):
    """
    try to use symlinks so breakpoints in the copied python files still work

    but some computers don't support symlinks so fall back to the copy method
    """
    try:
        symlink(src, dest)
    except OSError:
        copy(src, dest)


@fixture
def pytester_dir(pytester: Pytester, request: FixtureRequest) -> PytesterDir:
    """
    wrapper for pytester that moves the files located in
    `tests/fixtures/[test file]/[test name].py` to the pytester temp dir for the current test, so
    you don't have to write your test files as strings with the `makefile`/`makepyfile` methods
    """
    test = cast(Function, request.node)
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
        for file in (test_file_fixture_dir / f"{test_name}.{ext}" for ext in ("py", "robot")):
            if file.exists():
                try_symlink(file, pytester.path / file.name)
                break
        else:
            raise Exception(f"no fixtures found for {test_name=}")
    return cast(PytesterDir, pytester)


if TYPE_CHECKING:
    # Pytester is final so it's probably a bad idea to rely on extending this at runtime
    class PytesterDir(Pytester):  # pyright:ignore[reportGeneralTypeIssues]
        """
        fake subtype of `Pytester` that bans you from using file creation and runpytest methods.
        you should put real life files in `tests/fixtures/[test file path]/[test name]` instead,
        and use the runpytest methods on `PytestRobotTester` since they have handling for the xdist
        parameterization
        """

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
        def runpytest_inprocess(self, *args: str | PathLike[str], **kwargs: Never) -> Never: ...

        @override
        def runpytest_subprocess(
            self, *args: str | PathLike[str], timeout: float | None = None
        ) -> Never: ...

else:
    PytesterDir = Pytester


@fixture(params=[True, False], ids=["xdist_on", "xdist_off"])
def pr(pytester_dir: PytesterDir, request: FixtureRequest) -> PytestRobotTester:
    return PytestRobotTester(
        pytester=pytester_dir,
        xdist=2 if request.param else None,  # pyright:ignore[reportAny]
    )


def _log_file_exists():
    return Path("log.html").exists()


def _is_dunder(name: str) -> bool:
    return len(name) > 4 and name[:2] == name[-2:] == "__" and name[2] != "_" and name[-3] != "_"


def _is_element_list(xpath_object: _XPathObject) -> TypeGuard[list[_Element]]:
    result = isinstance(xpath_object, list)
    if result and xpath_object:
        return isinstance(xpath_object[0], _Element)
    return result


@final
class _XmlElement(Iterable["_XmlElement"]):
    def __init__(self, element: _Element) -> None:
        super().__init__()
        self._proxied = element

    @override
    def __getattribute__(self, /, name: str) -> object:
        if _is_dunder(name) or name not in vars(_Element):
            return super().__getattribute__(name)  # pyright:ignore[reportAny]
        return getattr(self._proxied, name)  # pyright:ignore[reportAny]

    def __bool__(self) -> Literal[True]:
        return True

    def __len__(self) -> Never:
        raise Exception(
            "cannot call `len()` on `XmlElement` to count its children, use `count_children` "
            "instead"
        )

    @override
    def __iter__(self) -> Iterator[_XmlElement]:
        for element in self._proxied:
            yield _XmlElement(element)

    def xpath(
        self,
        _path: _AnyStr,
        namespaces: _NonDefaultNSMapArg | None = ...,
        extensions: object = ...,
        smart_strings: bool = ...,  # noqa:FBT001
        **_variables: _XPathObject,
    ) -> _XPathObject:
        result = self._proxied.xpath(_path, namespaces, extensions, smart_strings, **_variables)
        if _is_element_list(result):
            # variance moment, but we aren't storing the value anywhere so it's fine
            return [_XmlElement(element) for element in result]  # pyright:ignore[reportReturnType]
        return result

    def count_children(self) -> int:
        return len(self._proxied)


if TYPE_CHECKING:

    class XmlElement(_Element):
        """
        proxy for lxml's `_Element` that disables its stupid nonsense `__bool__` and `__len__`
        behavior
        """

        def __init__(self, element: _Element) -> None: ...

        def __bool__(self) -> Literal[True]:  # pyright:ignore[reportReturnType]
            """normally this returns `True` only if it has children"""

        @override
        def __len__(self) -> Never:  # pyright:ignore[reportReturnType]
            """
            normally this returns how many children it has. but if you want to check than then
            call `count_children` instead
            """

        def count_children(self) -> int: ...

else:
    XmlElement = _XmlElement


def output_xml() -> XmlElement:
    return XmlElement(XML(Path("output.xml").read_bytes()))


def xpath(xml: _Element, query: str) -> XmlElement:
    results = xml.xpath(query)
    assert isinstance(results, list)
    (result,) = results
    assert isinstance(result, _Element)
    return XmlElement(result)


def assert_robot_total_stats(*, passed: int = 0, skipped: int = 0, failed: int = 0):
    root = output_xml()
    statistics = next(child for child in root if child.tag == "statistics")
    total = next(child for child in statistics if child.tag == "total")
    result = copy_object(next(child for child in total if child.tag == "stat").attrib)
    assert result == {"pass": str(passed), "fail": str(failed), "skip": str(skipped)}


@final
class PytestRobotTester:
    def __init__(self, *, pytester: PytesterDir, xdist: int | None):
        super().__init__()
        self.pytester = pytester
        self.xdist = xdist

    @staticmethod
    def assert_log_file_doesnt_exist():
        assert not _log_file_exists()

    def assert_log_file_exists(self, *, check_xdist: bool = True):
        """
        asserts that robot generated a log file, and ensures that it did/didn't use xdist.

        set `check_xdist` to `False` if you expect no tests to have been run (in which case most
        of the xdist-specific logic won't get hit so the xdist check would fail)
        """
        assert _log_file_exists()
        # far from perfect but we can be reasonably confident that the xdist stuff ran if this
        # folder exists
        if check_xdist or not self.xdist:
            assert bool(self.xdist) == bool(list(self.pytester.path.glob("**/robot_xdist_outputs")))

    @overload
    def run_and_assert_assert_pytest_result(
        self,
        *pytest_args: str,
        subprocess: Literal[False],
        plugins: list[object] | None = None,
        passed: int = 0,
        skipped: int = 0,
        failed: int = 0,
        errors: int = 0,
        xfailed: int = 0,
        exit_code: ExitCode | None = None,
    ) -> None: ...

    @overload
    def run_and_assert_assert_pytest_result(
        self,
        *pytest_args: str,
        subprocess: bool = ...,
        passed: int = 0,
        skipped: int = 0,
        failed: int = 0,
        errors: int = 0,
        xfailed: int = 0,
        exit_code: ExitCode | None = None,
    ) -> None: ...

    def run_and_assert_assert_pytest_result(
        self,
        *pytest_args: str,
        subprocess: bool = True,
        plugins: list[object] | None = None,
        passed: int = 0,
        skipped: int = 0,
        failed: int = 0,
        errors: int = 0,
        xfailed: int = 0,
        exit_code: ExitCode | None = None,
    ):
        # checked by the overloads
        result = self.run_pytest(*pytest_args or [], subprocess=subprocess, plugins=plugins)  # pyright:ignore[reportArgumentType]

        # this is kinda hueristic and gross, but i cant think of a clean way to add this check to
        # every test so this will do for now
        if not errors and exit_code != ExitCode.INTERNAL_ERROR:
            for line in result.errlines:
                if line.startswith("[ ERROR ] "):
                    raise Exception(
                        f"robot error detected in a test that expected no errors: {line}"
                    )
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
                    "cannot specify expected pytest outcomes when expected exit code is USAGE_ERROR"
                )
        else:
            result.assert_outcomes(
                passed=passed, skipped=skipped, failed=failed, errors=errors, xfailed=xfailed
            )
        try:
            assert result.ret == exit_code
        except AssertionError:
            if self.xdist:
                # workaround for https://github.com/pytest-dev/pytest-xdist/issues/1017
                assert (exit_code != ExitCode.OK) == any(
                    line for line in result.outlines if line.startswith("INTERNALERROR>")
                )
            else:
                raise

    @overload
    def run_pytest(
        self, *args: str, subprocess: Literal[False], plugins: list[object] | None = None
    ) -> RunResult: ...

    @overload
    def run_pytest(self, *args: str, subprocess: bool = ...) -> RunResult: ...

    def run_pytest(
        self, *args: str, subprocess: bool = True, plugins: list[object] | None = None
    ) -> RunResult:
        if self.xdist is not None:
            args += ("-n", str(self.xdist))
        pytester = cast(Pytester, self.pytester)
        return (
            pytester.runpytest_subprocess(*args)
            if subprocess
            else pytester.runpytest(*args, plugins=plugins or [])
        )

    def run_and_assert_result(
        self,
        *pytest_args: str,
        subprocess: bool = True,
        passed: int = 0,
        skipped: int = 0,
        failed: int = 0,
        errors: int = 0,
        xfailed: int = 0,
        exit_code: ExitCode | None = None,
    ):
        self.run_and_assert_assert_pytest_result(
            *pytest_args,
            subprocess=subprocess,
            passed=passed,
            skipped=skipped,
            failed=failed,
            errors=errors,
            xfailed=xfailed,
            exit_code=exit_code,
        )
        assert_robot_total_stats(
            passed=passed,
            # most things that are errors in pytest are failures in robot. also robot doesn't store
            #  errors here
            # TODO: a way to check for robot errors, i think they currently go undetected
            #  https://github.com/DetachHead/pytest-robotframework/issues/39
            failed=failed + errors,
            # robot doesn't have xfail, uses skips instead
            skipped=skipped + xfailed,
        )
