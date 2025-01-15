from __future__ import annotations

from robot.libraries.BuiltIn import BuiltIn

from pytest_robotframework import set_variables

set_variables({"foo": "bar\\baz"})


def test_asdf():
    assert BuiltIn().get_variable_value("$foo") == "bar\\baz"
