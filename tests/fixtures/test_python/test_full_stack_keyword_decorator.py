from __future__ import annotations

from pytest_robotframework import keyword


@keyword
def bar():
    raise Exception


def test_keyword():
    bar()
