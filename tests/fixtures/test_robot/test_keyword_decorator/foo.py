from __future__ import annotations

from robot.api import logger

from pytest_robotframework import keyword


@keyword  # ty: ignore[deprecated] wrong overload being matched due to https://github.com/astral-sh/ty/issues/128
def bar():
    logger.info("1")
