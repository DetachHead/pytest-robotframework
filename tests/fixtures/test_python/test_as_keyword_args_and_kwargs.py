from __future__ import annotations

from pytest_robotframework import as_keyword


def test_foo():
    with as_keyword("asdf", args=["a", "b"], kwargs={"c": "d", "e": "f"}):
        ...
