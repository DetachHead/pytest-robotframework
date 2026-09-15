from __future__ import annotations


# https://github.com/astral-sh/ruff/issues/7286
def pytest_robot_modify_args(collect_only: bool):  # ruff: ignore[boolean-type-hint-positional-argument]
    assert collect_only
