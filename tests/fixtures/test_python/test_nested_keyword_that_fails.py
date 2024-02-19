from __future__ import annotations

from pytest_robotframework import keyword


@keyword
def bar():
    raise Exception("asdf")


@keyword
def foo():
    bar()


def test_foo():
    foo()
