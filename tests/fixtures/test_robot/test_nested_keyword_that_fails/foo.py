from __future__ import annotations

from pytest_robotframework import keyword


@keyword
def baz():
    raise Exception("asdf")


@keyword
def bar():
    baz()
