from __future__ import annotations

from exceptiongroup import ExceptionGroup
from pytest import RaisesGroup


def test_foo():
    # keywordified in plugin.py
    exceptions = (ZeroDivisionError, TypeError)
    # https://github.com/astral-sh/ty/issues/247 and/or https://github.com/astral-sh/ty/issues/493
    with RaisesGroup(*exceptions):  # ty:ignore[no-matching-overload]
        raise ExceptionGroup("asdf", [cls() for cls in exceptions])
