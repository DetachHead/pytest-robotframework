# noqa: INP001
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.fixtures.test_python.test_keywordify_module import foo
else:
    import foo


from pytest_robotframework import keywordify

keywordify(foo, ["patched_keyword"])
