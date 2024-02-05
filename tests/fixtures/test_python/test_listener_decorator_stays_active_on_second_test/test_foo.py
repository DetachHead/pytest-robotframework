# noqa: INP001
# init file breaks it and i dont care because i hate init files
from __future__ import annotations

from typing import TYPE_CHECKING

# needed because the import needs to be different after the file is moved
if TYPE_CHECKING:
    from tests.fixtures.test_python.test_listener_decorator import conftest
else:
    import conftest


def test_listener():
    assert conftest.ran


def test_listener2():
    assert conftest.ran
