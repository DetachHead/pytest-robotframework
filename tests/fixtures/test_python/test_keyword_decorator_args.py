from __future__ import annotations

from pytest_robotframework import keyword


@keyword
def foo(*args: object, **kwargs: object):  # noqa: ARG001
    ...


def test_keyword_decorator_with_args():
    foo(1, bar=True)
