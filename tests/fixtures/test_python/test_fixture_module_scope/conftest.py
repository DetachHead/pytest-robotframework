from __future__ import annotations

from pytest import fixture

count = 0


@fixture(scope="session")
def thing() -> int:
    global count
    count += 1
    return count
