# noqa: INP001
# init file breaks it
from robot import model, result
from robot.api.interfaces import ListenerV3
from typing_extensions import override

from pytest_robotframework import listener

ran = False


@listener
class Listener(ListenerV3):
    @override
    def start_test(
        self,
        data: model.TestCase,
        result: result.TestCase,  # pylint:disable=redefined-outer-name
    ):
        global ran
        ran = True
