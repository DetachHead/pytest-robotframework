from __future__ import annotations

from exceptiongroup import ExceptionGroup
from pytest import RaisesGroup


def test_foo():
    # keywordified in plugin.py
    exceptions = (ZeroDivisionError, TypeError)
    with RaisesGroup(*exceptions):
        raise ExceptionGroup("asdf", [cls() for cls in exceptions])
