from __future__ import annotations

from pytest import raises

from pytest_robotframework import keyword


class FooError(Exception):
    pass


@keyword
def bar():
    raise FooError


def test_foo():
    with raises(FooError):
        bar()
