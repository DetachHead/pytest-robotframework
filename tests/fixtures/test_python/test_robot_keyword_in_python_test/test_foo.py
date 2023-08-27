# noqa: INP001
# init file breaks it and i dont care
from robot.libraries.BuiltIn import BuiltIn

from pytest_robotframework import import_resource

import_resource("bar.resource")


def test_foo():
    BuiltIn().run_keyword("bar")
