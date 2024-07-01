from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import Item, Session, StashKey, hookimpl

if TYPE_CHECKING:
    from collections.abc import Iterator

run_key = StashKey[int]()


@hookimpl(wrapper=True)
def pytest_runtest_protocol(item: Item) -> Iterator[None]:
    item.session.stash[run_key] = 1
    yield
    item.session.stash[run_key] += 1


def pytest_sessionfinish(session: Session):
    assert session.stash[run_key] == 2
