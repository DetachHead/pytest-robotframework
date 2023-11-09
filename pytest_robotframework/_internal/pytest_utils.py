from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from pytest_robotframework._internal.cringe_globals import current_session
from pytest_robotframework._internal.errors import InternalError

if TYPE_CHECKING:
    from basedtyping import T
    from pytest import Item, Session, StashKey


def init_stash(  # pylint:disable=missing-param-doc
    key: StashKey[T],
    initializer: Callable[[], T],
    session_or_item: Session | Item | None = None,
) -> T:
    """gets the value for a pytest stashed key, or initializes it with a value if it's not there

    :param session_or_item: defaults to the current session"""
    if not session_or_item:
        session_or_item = current_session()
        if not session_or_item:
            raise InternalError(f"failed to get session for {key!s}")
    if key in session_or_item.stash:
        return session_or_item.stash[key]
    result = initializer()
    session_or_item.stash[key] = result
    return result
