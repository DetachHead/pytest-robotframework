# noqa: N999
# robot class libraries need to have the same name as the module
from __future__ import annotations

from robot.api import logger

from pytest_robotframework import keyword


class ClassLibrary:
    def __init__(self):
        pass

    @keyword
    def foo(self):  # noqa: PLR6301
        logger.info("hi")
