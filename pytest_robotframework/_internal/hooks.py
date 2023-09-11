from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Session

# ruff: noqa: ARG001


def pytest_robot_modify_args(args: list[str], session: Session) -> None:
    """modify the arguments passed to robot in-place"""
