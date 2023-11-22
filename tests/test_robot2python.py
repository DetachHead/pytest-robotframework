from __future__ import annotations

from ast import parse
from os import listdir
from pathlib import Path

from pytest import mark

from pytest_robotframework._internal.utils import unparse
from pytest_robotframework.robot2python import _convert

current_file = Path(__file__)
fixtures_folder = current_file.parent / f"fixtures/{current_file.stem}"


def format_code(code: str) -> str:
    """hacky way to format code however the ast unparser does. would use black but it's a pain to
    run programmatically"""
    return unparse(parse(code))


@mark.parametrize(
    "suite", [fixtures_folder / suite for suite in listdir(fixtures_folder)]
)
def test_robot2python(suite: Path):
    converted_tests = _convert(suite, suite)
    for expected_python_file, actual_python_code in converted_tests.items():
        assert format_code(expected_python_file.read_text()) == format_code(
            actual_python_code
        )
    assert len(converted_tests) == len(list(suite.glob("**/*.py")))
