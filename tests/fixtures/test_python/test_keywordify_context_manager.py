from __future__ import annotations

from pytest import raises


def test_foo():
    # keywordified in plugin.py
    with raises(ZeroDivisionError):
        _ = 1 / 0
