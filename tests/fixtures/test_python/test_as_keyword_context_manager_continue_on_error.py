from __future__ import annotations

from robot.api import logger

from pytest_robotframework import as_keyword


def test_foo():
    with as_keyword("hi", continue_on_failure=True) as result:
        assert 1 == 2  # type:ignore[comparison-overlap] # noqa: PLR0133
    logger.info(2)  # type:ignore[no-untyped-call]
    assert isinstance(result.value, AssertionError)
