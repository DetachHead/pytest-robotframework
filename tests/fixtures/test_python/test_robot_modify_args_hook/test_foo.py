from __future__ import annotations

from robot.libraries.BuiltIn import BuiltIn


def test_foo():
    assert BuiltIn().get_variable_value("$foo") == "bar"  # ty:ignore[call-non-callable] robot types are messed up
