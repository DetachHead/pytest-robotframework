from __future__ import annotations

from pytest_robotframework import keyword


@keyword(name="foo bar", tags=("a", "b"))  # ty: ignore[deprecated] wrong overload being matched due to https://github.com/astral-sh/ty/issues/128
def foo(): ...


def test_docstring():
    foo()
