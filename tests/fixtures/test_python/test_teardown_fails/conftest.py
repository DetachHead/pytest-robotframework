from __future__ import annotations


def pytest_runtest_teardown():
    raise Exception("2")
