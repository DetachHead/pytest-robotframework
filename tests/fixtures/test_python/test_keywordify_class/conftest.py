# noqa: INP001
from __future__ import annotations

from pytest_robotframework import keywordify


class Foo:
    def patched_keyword(self):
        pass


keywordify(Foo)
