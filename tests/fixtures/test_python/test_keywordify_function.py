from __future__ import annotations

from pytest import fail


def test_foo():
    # keywordified in plugin.py
    # https://github.com/astral-sh/ty/issues/553
    fail("asdf")  # ty:ignore[call-non-callable]
