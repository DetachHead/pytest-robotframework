from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from robot.api import logger

from pytest_robotframework import as_keyword

if TYPE_CHECKING:
    from typing_extensions import assert_type


def test_foo():
    with as_keyword("hi") as result:
        logger.info(1)  # type:ignore[no-untyped-call]
    logger.info(2)  # type:ignore[no-untyped-call]
    if TYPE_CHECKING:
        # make sure "FAIL" isn't a possible value when `on_failure` is "raise now"
        assert_type(result.value, Literal["PASS", None])
    assert result.value == "PASS"
