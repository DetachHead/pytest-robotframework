from __future__ import annotations

from pytest import skip


def pytest_runtest_setup():
    # https://github.com/astral-sh/ty/issues/553
    skip()  # ty:ignore[call-non-callable]
