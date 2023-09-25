from __future__ import annotations

from contextlib import AbstractContextManager, contextmanager
from typing import TYPE_CHECKING

from pytest_robotframework import keyword

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from typing import assert_type


@keyword(name="foo bar", tags=("a", "b"))
def foo(): ...


@keyword(name="foo bar", tags=("a", "b"))
@contextmanager
def bar() -> Iterator[None]:
    yield


# type tests
if TYPE_CHECKING:
    assert_type(foo, Callable[[], None])
    assert_type(bar, Callable[[], AbstractContextManager[None]])


def test_docstring():
    foo()
