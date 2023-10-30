from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Iterator

if TYPE_CHECKING:
    from contextlib import (
        AbstractContextManager,
        _GeneratorContextManager,
        contextmanager,
    )

    from typing_extensions import Never, assert_type

    from pytest_robotframework import keyword

    # keyword, args:
    @keyword(name="foo bar", tags=("a", "b"))
    def a(): ...

    assert_type(a, Callable[[], None])

    # keyword, no args:
    @keyword
    def g(): ...

    assert_type(g, Callable[[], None])

    # keyword, no args, returns Never:
    @keyword  # make sure there's no deprecation warning here
    def h() -> Never: ...

    assert_type(h, Callable[[], Never])

    # keyword, wrap_context_manager=True:
    @keyword(wrap_context_manager=True)
    @contextmanager
    def b() -> Iterator[None]:
        yield

    assert_type(b, Callable[[], AbstractContextManager[None]])

    # keyword, wrap_context_manager=False:
    @keyword(wrap_context_manager=False)
    @contextmanager
    def c() -> Iterator[None]:
        yield

    assert_type(c, Callable[[], _GeneratorContextManager[None]])

    # keyword, context manager with no wrap_context_manager arg:
    @keyword
    @contextmanager
    def d() -> Iterator[None]:
        yield

    assert_type(d, Never)

    # keyword, non-context manager with wrap_context_manager=True:
    # expected type error
    @keyword(wrap_context_manager=True)  # type:ignore[arg-type]
    def e(): ...

    # keyword, non-context manager with wrap_context_manager=False:
    # expected type error
    @keyword(wrap_context_manager=False)  # type:ignore[type-var]
    def f(): ...
