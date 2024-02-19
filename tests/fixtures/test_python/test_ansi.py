from __future__ import annotations


def test_asdf():
    assert [1, 2, 3] == [1, "<div>asdf</div>", 3]
