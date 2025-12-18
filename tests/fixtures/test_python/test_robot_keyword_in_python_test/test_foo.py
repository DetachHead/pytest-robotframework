from __future__ import annotations

from pytest_robotframework import import_resource
from pytest_robotframework._internal.robot.utils import run_keyword

import_resource("bar/bar.resource")


def test_foo():
    run_keyword("bar")
