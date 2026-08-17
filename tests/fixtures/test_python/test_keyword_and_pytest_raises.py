from __future__ import annotations

from pytest import raises

from pytest_robotframework import keyword


class FooError(Exception):
    pass


@keyword  # ty: ignore[deprecated] wrong overload being matched due to https://github.com/astral-sh/ty/issues/128
def bar():
    raise FooError


def test_foo():
    with raises(FooError):
        bar()
