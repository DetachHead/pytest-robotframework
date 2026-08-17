from __future__ import annotations

from pytest_robotframework import keyword


@keyword(max_argument_length_in_log=60)  # ty: ignore[deprecated] wrong overload being matched due to https://github.com/astral-sh/ty/issues/128
def foo(*args: object, **kwargs: object):  # pyright:ignore[reportUnusedParameter]
    ...


def test_no_truncation():
    foo(1, bar=True)


def test_truncation():
    foo("a" * 61, bar="b" * 61)
