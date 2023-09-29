from __future__ import annotations

from pytest_robotframework import keyword


@keyword
def foo():
    """
    hie

    :returns: asdf
    """


def test_docstring():
    foo()
