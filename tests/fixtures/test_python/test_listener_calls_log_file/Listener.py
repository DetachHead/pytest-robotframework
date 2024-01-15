# noqa: INP001
# init file breaks it and i dont care because i hate init files
from __future__ import annotations

from pathlib import Path

from robot.api.interfaces import ListenerV3
from typing_extensions import override


class Listener(ListenerV3):
    @override
    def log_file(self, path: Path):
        # TODO: this doesnt log to the console so no other way to verify that it ran
        #  https://github.com/DetachHead/pytest-robotframework/issues/39
        _ = Path("hi").write_text("")
