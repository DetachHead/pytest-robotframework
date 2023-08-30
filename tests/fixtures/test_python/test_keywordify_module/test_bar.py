# noqa: INP001
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.fixtures.test_python.test_keywordify_module.foo import patched_keyword
else:
    from foo import patched_keyword


def test_bar():
    patched_keyword()
