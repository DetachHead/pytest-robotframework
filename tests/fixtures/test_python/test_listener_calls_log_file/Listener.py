# noqa: N999
# module needs to have the same name as the class when registering the listener with the cli
from __future__ import annotations

from pathlib import Path

from robot.api.interfaces import ListenerV3
from typing_extensions import override


class Listener(ListenerV3):
    @override
    def log_file(self, path: Path):
        # TODO: this doesnt log to the console so no other way to verify that it ran
        #  https://github.com/DetachHead/pytest-robotframework/issues/39
        _ = Path("hi").write_text("", encoding="utf-8")
