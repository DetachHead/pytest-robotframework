from __future__ import annotations

from pytest import mark


@mark.skipif(condition=True, reason="foo")
def test_one_test_skipped():
    raise Exception("asdf")
