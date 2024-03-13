from __future__ import annotations


def test_foo(): ...


class TestBar:
    class TestBaz:
        @staticmethod
        def test_baz(): ...

    @staticmethod
    def test_bar(): ...
