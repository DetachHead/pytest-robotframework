from __future__ import annotations

from pathlib import Path
from shutil import copy, copytree
from types import ModuleType
from typing import cast

from pytest import FixtureRequest, Function, Pytester, fixture

from tests.utils import PytesterDir

pytest_plugins = ["pytester"]


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
        copytree(fixture_dir_for_current_test, pytester.path, dirs_exist_ok=True)
    else:
        for file in (
            test_file_fixture_dir / f"{test_name}.{ext}" for ext in ("py", "robot")
        ):
            if file.exists():
                copy(file, pytester.path)
                break
        else:
            raise Exception(f"no fixtures found for {test_name=}")
    return cast(PytesterDir, pytester)
