from __future__ import annotations

from pytest import skip


def pytest_runtest_teardown():
    # https://github.com/astral-sh/ty/issues/553
    skip()  # ty:ignore[call-non-callable]
