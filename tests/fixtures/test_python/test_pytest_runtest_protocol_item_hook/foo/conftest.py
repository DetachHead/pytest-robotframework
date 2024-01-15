from __future__ import annotations

from typing import Iterator

from pytest import Item, Session, StashKey, hookimpl

run_key = StashKey[int]()


@hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: Item) -> Iterator[None]:
    item.session.stash[run_key] = 1
    yield
    item.session.stash[run_key] += 1


def pytest_sessionfinish(session: Session):
    assert session.stash[run_key] == 2
