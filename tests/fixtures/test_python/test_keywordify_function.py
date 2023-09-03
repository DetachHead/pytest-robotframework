from __future__ import annotations

from pytest import fail


def test_foo():
    # keywordified in plugin.py
    fail("asdf")
