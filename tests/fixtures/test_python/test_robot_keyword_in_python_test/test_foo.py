from __future__ import annotations

from robot.libraries.BuiltIn import BuiltIn

from pytest_robotframework import import_resource

import_resource("bar/bar.resource")


def test_foo():
    BuiltIn().run_keyword("bar")
