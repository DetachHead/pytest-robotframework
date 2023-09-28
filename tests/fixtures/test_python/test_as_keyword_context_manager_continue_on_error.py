from __future__ import annotations

from robot.api import logger

from pytest_robotframework import as_keyword


class FooError(Exception):
    pass


def test_foo():
    with as_keyword("hi", continue_on_failure=True) as result:
        raise FooError
    logger.info(2)  # type:ignore[no-untyped-call]
    assert isinstance(result.value, FooError)
