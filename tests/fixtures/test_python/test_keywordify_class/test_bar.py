# noqa: INP001
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.fixtures.test_python.test_keywordify_class.conftest import Foo
else:
    from conftest import Foo


def test_bar():
    Foo().patched_keyword()
