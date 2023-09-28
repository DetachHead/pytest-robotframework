from __future__ import annotations

from abc import abstractmethod
from contextlib import AbstractContextManager
from functools import wraps
from typing import TYPE_CHECKING, Callable, cast

from basedtyping import T, T_co
from typing_extensions import Concatenate, ParamSpec, override

if TYPE_CHECKING:
    from types import TracebackType

P = ParamSpec("P")


def patch_method(  # type: ignore[no-any-explicit]
    cls: type[object],
    method_name: str | None = None,
    # https://github.com/python/mypy/issues/15073
    # ) -> Callable[[Callable[Concatenate[Callable[P, T], P], T]], Callable[P, T]]:
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """replaces a method of a class with the decorated one

    example:
    -------
    >>> class Foo:
    ...     def foo(self) -> int:
    ...         return 1
    ...
    ... @patch_method(Foo)
    ... def foo(old_method: Callable[[Foo], int], self: Foo) -> int:
    ...     return old_method(self) + 1
    ...
    ... print(Foo().foo()) # 2

    :param method_name: defaults to the name of the function being decorated
    """

    def decorator(fn: Callable[Concatenate[Callable[P, T], P], T]) -> Callable[P, T]:
        nonlocal method_name
        if method_name is None:
            method_name = fn.__name__
        old_method = cast(Callable[P, T], getattr(cls, method_name))

        @wraps(fn)
        def new_fn(*args: P.args, **kwargs: P.kwargs) -> T:
            return fn(old_method, *args, **kwargs)

        setattr(cls, method_name, new_fn)
        return new_fn

    return decorator


class ContextManager(AbstractContextManager[T_co]):
    """removes `None` from the return type of `AbstractContextManager.__exit__` to prevent code from
    being incorrectly marked as unreachable by mypy and pyright. see these issues:
    - https://github.com/python/mypy/issues/15158
    - https://github.com/microsoft/pyright/issues/6034
    """

    @abstractmethod
    @override
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
        /,
    ) -> bool: ...
