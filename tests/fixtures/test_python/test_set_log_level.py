from __future__ import annotations

from robot.api.logger import debug
from robot.libraries.BuiltIn import BuiltIn


def test_asdf():
    BuiltIn().set_log_level("DEBUG")
    debug("hello???")
