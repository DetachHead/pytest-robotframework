from __future__ import annotations

from robot.api import logger

from pytest_robotframework import as_keyword


def test_foo():
    with as_keyword("hi", on_failure="ignore") as result:
        logger.info(1)  # type:ignore[no-untyped-call]
    logger.info(2)  # type:ignore[no-untyped-call]
    assert result.value == "PASS"
