from __future__ import annotations

from pytest_robotframework import keyword


@keyword
def foo(): ...


@keyword
def bar():
    foo()
    foo()
