from __future__ import annotations

from pytest_robotframework import as_keyword, keyword


def foo():
    with as_keyword("ah yes"):
        bar()


@keyword
def bar():
    raise Exception


def test_as_keyword():
    foo()
