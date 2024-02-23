from __future__ import annotations

from abc import abstractmethod
from functools import wraps
from typing import TYPE_CHECKING, Callable, ContextManager, Protocol, cast

from basedtyping import P, T, out_T
from typing_extensions import override

if TYPE_CHECKING:
    from types import TracebackType

    from typing_extensions import Concatenate


def patch_method(
    cls: type[object], method_name: str | None = None
) -> Callable[[Callable[Concatenate[Callable[P, T], P], T]], Callable[P, T]]:
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


class SuppressableContextManager(ContextManager[out_T], Protocol[out_T]):
    """removes `None` from the return type of `AbstractContextManager.__exit__` to prevent code
    from being incorrectly marked as unreachable by pyright. see https://github.com/microsoft/pyright/issues/6034
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


main_package_name = __name__.split(".")[0]
"""the name of the top level package (should be `pytest_robotframework`)"""
