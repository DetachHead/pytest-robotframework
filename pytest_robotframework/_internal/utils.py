from __future__ import annotations

from functools import wraps
from typing import TYPE_CHECKING, Callable, cast

from basedtyping import P, T

if TYPE_CHECKING:
    from typing_extensions import Concatenate


def patch_method(
    cls: type[object], method_name: str | None = None
) -> Callable[[Callable[Concatenate[Callable[P, T], P], T]], Callable[P, T]]:
    """
    replaces a method of a class with the decorated one

    example:
    -------
    >>> class Foo:
    ...     def foo(self) -> int:
    ...         return 1
    ...
    ...
    ... @patch_method(Foo)
    ... def foo(old_method: Callable[[Foo], int], self: Foo) -> int:
    ...     return old_method(self) + 1
    ...
    ...
    ... print(Foo().foo())  # 2

    :param method_name: defaults to the name of the function being decorated
    """

    def decorator(fn: Callable[Concatenate[Callable[P, T], P], T]) -> Callable[P, T]:
        nonlocal method_name
        # https://github.com/astral-sh/ty/issues/220
        if method_name is None:  # ty:ignore[unresolved-reference]
            # https://github.com/astral-sh/ty/issues/599
            method_name = fn.__name__  # ty:ignore[unresolved-attribute]
        old_method = cast(
            Callable[P, T],
            # https://github.com/astral-sh/ty/issues/220
            getattr(cls, method_name),  # ty:ignore[possibly-unresolved-reference]
        )

        @wraps(fn)
        def new_fn(*args: P.args, **kwargs: P.kwargs) -> T:
            return fn(old_method, *args, **kwargs)

        setattr(cls, method_name, new_fn)  # ty:ignore[possibly-unresolved-reference]
        return new_fn

    return decorator


main_package_name = __name__.split(".")[0]
"""the name of the top level package (should be `pytest_robotframework`)"""
