from __future__ import annotations

from typing import TYPE_CHECKING

from robot.api import logger

from pytest_robotframework import as_keyword

if TYPE_CHECKING:
    from typing_extensions import assert_type


def test_foo():
    with as_keyword("hi") as result:
        logger.info(1)  # type:ignore[no-untyped-call]
    logger.info(2)  # type:ignore[no-untyped-call]
    # make sure result can't be used unless continue_on_failure is enabled
    if TYPE_CHECKING:
        assert_type(result.value, None)
    assert result.value is None
