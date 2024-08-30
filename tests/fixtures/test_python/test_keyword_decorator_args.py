from __future__ import annotations

from pytest_robotframework import keyword


@keyword
def foo(*args: object, **kwargs: object):  # pyright:ignore[reportUnusedParameter]
    ...


def test_no_truncation():
    foo(1, bar=True)


def test_truncation():
    foo("a" * 51, bar="b" * 51)
