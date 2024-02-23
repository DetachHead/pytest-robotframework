from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import Item, StashKey

if TYPE_CHECKING:
    from pluggy import Result

exception_key = StashKey[BaseException]()


def save_exception_to_item(item: Item, outcome: Result[object]):
    if outcome.exception:
        item.stash[exception_key] = outcome.exception
