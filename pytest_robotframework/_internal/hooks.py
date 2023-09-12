from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Session

# https://github.com/astral-sh/ruff/issues/7286
# ruff: noqa: ARG001, FBT001


def pytest_robot_modify_args(
    args: list[str], collect_only: bool, session: Session
) -> None:
    """modify the arguments passed to robot in-place"""
