from __future__ import annotations

from robot.libraries.BuiltIn import BuiltIn


def test_func():
    assert BuiltIn().get_variable_value("$foo") is None  # ty:ignore[call-non-callable] robot types are messed up
