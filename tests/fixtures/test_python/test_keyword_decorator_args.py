from __future__ import annotations

from pytest_robotframework import keyword


@keyword(max_argument_length_in_log=60)
def foo(*args: object, **kwargs: object):  # pyright:ignore[reportUnusedParameter]
    ...


def test_no_truncation():
    foo(1, bar=True)


def test_truncation():
    foo("a" * 61, bar="b" * 61)
