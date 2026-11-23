from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Callable, Generator
    from contextlib import (
        AbstractContextManager,
        _GeneratorContextManager,  # pyright:ignore[reportPrivateUsage]
        contextmanager,
    )
    from typing import Never, assert_type

    from pytest_robotframework import keyword

    # keyword, args:
    @keyword(name="foo bar", tags=("a", "b"))
    def a() -> None: ...

    # https://github.com/astral-sh/ty/issues/1495#issuecomment-3668125131

    _ = assert_type(a, Callable[[], None])  # ty:ignore[assert-type-unspellable-subtype]

    # keyword, no args:
    @keyword
    def b() -> None: ...

    _ = assert_type(b, Callable[[], None])  # ty:ignore[assert-type-unspellable-subtype]

    # keyword, no args, returns Never:
    @keyword  # make sure there's no deprecation warning here
    def c() -> Never:
        raise Exception

    _ = assert_type(c, Callable[[], Never])  # ty:ignore[type-assertion-failure]

    # keyword, wrap_context_manager=True:
    @keyword(wrap_context_manager=True)
    @contextmanager
    def d() -> Generator[None, None, None]:
        yield

    _ = assert_type(d, Callable[[], AbstractContextManager[None]])  # ty:ignore[type-assertion-failure]

    # keyword, wrap_context_manager=False:
    @keyword(wrap_context_manager=False)
    @contextmanager
    def e() -> Generator[None, None, None]:
        yield

    _ = assert_type(e, Callable[[], _GeneratorContextManager[None]])  # ty:ignore[type-assertion-failure]

    # keyword, context manager with no wrap_context_manager arg:
    @keyword  # pyright:ignore[reportDeprecated] # ty: ignore[deprecated] # pyrefly: ignore[deprecated]
    @contextmanager
    def f() -> Generator[None, None, None]:
        yield

    _ = assert_type(f, Never)

    # pyright doesn't report an error here due to https://github.com/microsoft/pyright/issues/11292
    @keyword()  # ty: ignore[deprecated] # pyrefly: ignore[deprecated]
    @contextmanager
    def g() -> Generator[None]:
        yield

    _ = assert_type(g, Never)

    # keyword, non-context manager with wrap_context_manager=True:
    # expected type error
    @keyword(wrap_context_manager=True)  # pyright:ignore[reportArgumentType]  # ty:ignore[invalid-argument-type] # pyrefly: ignore[bad-argument-type]
    def h() -> None: ...

    # keyword, non-context manager with wrap_context_manager=False:
    # expected type error
    @keyword(wrap_context_manager=False)  # pyright:ignore[reportArgumentType]  # ty:ignore[invalid-argument-type] # pyrefly: ignore[bad-specialization]
    def i() -> None: ...

    # keyword decorator on class
    @keyword
    class Foo: ...

    # ensure that the class can still be used as a type annotation
    foo: Foo = Foo()

    # keyword decorator on class with unnecessary call
    @keyword()
    class Bar: ...

    bar: Bar = Bar()

    # keyword decorator on class context manager
    @keyword(wrap_context_manager=True)
    class Baz(AbstractContextManager[None]):
        @override
        def __exit__(self, *_: object): ...

    # TODO: can we figure out a way to get this to work? we dont want to preserve the original type
    # because it's wrapped with a different unrelated type
    baz: Baz = Baz()  # ty: ignore[invalid-type-form] # pyright: ignore[reportGeneralTypeIssues]
