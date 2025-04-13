"""
cringe global variables for when there's no other way to get the current session/item. this
should only be used as a last resort

this is safe for now since robot doesn't support running multiple tests at the same time
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest import Item, Session

_current_item: Item | None = None
_current_session: Session | None = None


def current_item() -> Item | None:
    return _current_item


def current_session() -> Session | None:
    return _current_session
