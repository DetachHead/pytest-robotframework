from __future__ import annotations

from pytest_robotframework import keyword


@keyword(name="foo bar", tags=("a", "b"))
def foo(): ...


def test_docstring():
    foo()
