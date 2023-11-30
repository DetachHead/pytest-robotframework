from __future__ import annotations

from pathlib import Path
from shutil import copy, copytree
from sys import gettrace
from types import ModuleType
from typing import cast

from pytest import FixtureRequest, Function, Pytester, fixture

from tests.utils import PytesterDir

pytest_plugins = ["pytester"]


def copy_file_with_breakpoints(source_file: Path, destination_dir: Path):
    copy(source_file, destination_dir)
    destination_file_name = str(destination_dir / source_file.name)
    try:
        from pydevd import PyDevdAPI  # type:ignore[import-not-found] #noqa: PLC0415
    except ImportError:
        return
    pydevd_api = PyDevdAPI()  # type:ignore[no-any-expr]
    py_db = gettrace()._args[0]  # type:ignore[union-attr] #noqa: SLF001
    for _, (
        filename,
        breakpoint_type,
        breakpoint_id,
        line,
        condition,
        func_name,
        expression,
        suspend_policy,
        hit_condition,
        is_logpoint,
    ) in list(py_db.api_received_breakpoints.values())[:]:
        if Path(filename) == source_file:
            add_breakpoint_result = pydevd_api.add_breakpoint(  # type:ignore[no-any-expr]
                py_db=py_db,
                original_filename=destination_file_name,
                breakpoint_type=breakpoint_type,
                # TODO: better way to get a unique id
                breakpoint_id=breakpoint_id + 99999,
                line=line,
                condition=condition,
                func_name=func_name,
                expression=expression,
                suspend_policy=suspend_policy,
                hit_condition=hit_condition,
                is_logpoint=is_logpoint,
            )
            if (
                add_breakpoint_result.error_code  # type:ignore[no-any-expr]
                != PyDevdAPI.ADD_BREAKPOINT_NO_ERROR  # type:ignore[no-any-expr]
            ):
                raise Exception(
                    f"failed to copy breakpoints to fixture file ({source_file} ->"
                    f" {destination_file_name}): {add_breakpoint_result}"  # type:ignore[no-any-expr]
                )


@fixture  # type:ignore[no-any-expr]
def pytester_dir(pytester: Pytester, request: FixtureRequest) -> PytesterDir:
    """wrapper for pytester that moves the files located in
    `tests/fixtures/[test file]/[test name].py` to the pytester temp dir for the current test, so
    you don't have to write your test files as strings with the `makefile`/`makepyfile` methods
    """
    test = cast(Function, request.node)
    test_name = test.name
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
            copy_function=lambda src, dest: copy_file_with_breakpoints(
                Path(src), Path(dest)
            ),
        )
    else:
        for file in (
            test_file_fixture_dir / f"{test_name}.{ext}" for ext in ("py", "robot")
        ):
            if file.exists():
                copy_file_with_breakpoints(file, pytester.path)
                break
        else:
            raise Exception(f"no fixtures found for {test_name=}")
    return cast(PytesterDir, pytester)
