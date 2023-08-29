from __future__ import annotations

from robot.api.interfaces import ListenerV3

from pytest_robotframework import listener


@listener
class Listener(ListenerV3):
    pass


def test_listener():
    pass
