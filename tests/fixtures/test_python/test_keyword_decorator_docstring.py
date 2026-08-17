from __future__ import annotations

from pytest_robotframework import keyword


@keyword  # ty: ignore[deprecated] wrong overload being matched due to https://github.com/astral-sh/ty/issues/128
def foo():
    """hie"""


def test_docstring():
    foo()
