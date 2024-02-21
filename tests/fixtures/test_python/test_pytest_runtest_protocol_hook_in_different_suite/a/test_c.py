from __future__ import annotations

from pytest import mark

from pytest_robotframework import as_keyword


@mark.asdf
def test_asdf():
    with as_keyword("asdf"):
        assert True
