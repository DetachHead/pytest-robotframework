from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from collections.abc import Iterator
    from contextlib import (
        AbstractContextManager,
        _GeneratorContextManager,  # pyright:ignore[reportPrivateUsage]
        contextmanager,
    )

    from typing_extensions import Never, assert_type

    from pytest_robotframework import keyword

    # keyword, args:
    @keyword(name="foo bar", tags=("a", "b"))
    def a(): ...

    _ = assert_type(a, Callable[[], None])

    # keyword, no args:
    @keyword
    def g(): ...

    _ = assert_type(g, Callable[[], None])

    # keyword, no args, returns Never:
    @keyword  # make sure there's no deprecation warning here
    def h() -> Never: ...

    _ = assert_type(h, Callable[[], Never])

    # keyword, wrap_context_manager=True:
    @keyword(wrap_context_manager=True)
    @contextmanager
    def b() -> Iterator[None]:
        yield

    _ = assert_type(b, Callable[[], AbstractContextManager[None]])

    # keyword, wrap_context_manager=False:
    @keyword(wrap_context_manager=False)
    @contextmanager
    def c() -> Iterator[None]:
        yield

    _ = assert_type(c, Callable[[], _GeneratorContextManager[None]])

    # keyword, context manager with no wrap_context_manager arg:
    @keyword  # pyright:ignore[reportDeprecated]
    @contextmanager
    def d() -> Iterator[None]:
        yield

    _ = assert_type(d, Never)

    # keyword, non-context manager with wrap_context_manager=True:
    # expected type error
    @keyword(wrap_context_manager=True)  # pyright:ignore[reportArgumentType]
    def e(): ...

    # keyword, non-context manager with wrap_context_manager=False:
    # expected type error
    @keyword(wrap_context_manager=False)  # pyright:ignore[reportArgumentType]
    def f(): ...
