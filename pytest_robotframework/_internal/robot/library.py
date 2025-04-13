"""
robot library that contains the keywords added by the plugin. this module is imported as a robot
library by `robot_classes.PytestRuntestProtocolInjector`
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Literal

from _pytest._code.code import TerminalRepr
from _pytest.runner import (
    call_and_report,  # pyright:ignore[reportUnknownVariableType]
    show_test_item,
)
from pytest import Item, StashKey, TestReport
from robot.libraries.BuiltIn import BuiltIn

from pytest_robotframework import (
    _get_status_reporter_failures,  # pyright:ignore[reportPrivateUsage]
    keyword,
)
from pytest_robotframework._internal import cringe_globals
from pytest_robotframework._internal.errors import InternalError
from pytest_robotframework._internal.pytest.exception_getter import exception_key

if TYPE_CHECKING:
    from pytest_robotframework._internal.robot.utils import Cloaked

_report_key = StashKey[list[TestReport]]()

ROBOT_AUTO_KEYWORDS: Final = False


def _call_and_report_robot_edition(
    item: Item, when: Literal["setup", "call", "teardown"], **kwargs: object
):
    """
    wrapper for the `call_and_report` function used by `_pytest.runner.runtestprotocol`
    with additional logic to show the result in the robot log
    """
    reports = item.stash.setdefault(_report_key, [])
    report = call_and_report(item, when, log=True, **kwargs)
    reports.append(report)
    if report.skipped:
        # empty string means xfail with no reason, None means it was not an xfail
        xfail_reason = report.wasxfail if hasattr(report, "wasxfail") else None
        if xfail_reason is None:
            skip_reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else ""
        else:
            skip_reason = "xfail" + (f": {xfail_reason}" if xfail_reason else "")
        BuiltIn().skip(skip_reason)
    elif report.failed:
        # make robot show the exception:
        exception = item.stash.get(exception_key, None)
        if exception:
            status_reporter_exception = _get_status_reporter_failures(exception)
            if status_reporter_exception:
                # the exception was already raised and logged inside a keyword, so raise the
                # ExecutionFailed which will just tell robot that the test failed without logging
                # the failure again
                raise status_reporter_exception[-1]
            # tell robot the test failed and also add the failure to the log
            raise exception
        longrepr = report.longrepr
        if isinstance(longrepr, str):
            # xfail strict and errors caught in our pytest_runtest_makereport hook
            raise Exception(longrepr)
        if isinstance(longrepr, TerminalRepr):
            # errors such as invalid fixture (FixtureLookupErrorRepr)
            raise Exception(str(longrepr))
        raise InternalError(
            f"failed to get exception from failed test ({item=}, {when=}): {longrepr!s}"
        )


@keyword
def setup(arg: Cloaked[Item]):
    item = arg.value
    cringe_globals._current_item = item  # pyright:ignore[reportPrivateUsage]
    # mostly copied from the start of `_pytest.runner.runtestprotocol`:
    if (
        hasattr(item, "_request") and not item._request  # pyright:ignore[reportAttributeAccessIssue,reportUnknownMemberType]
    ):
        # This only happens if the item is re-run, as is done by
        # pytest-rerunfailures.
        item._initrequest()  # pyright:ignore[reportAttributeAccessIssue,reportUnknownMemberType]
    _call_and_report_robot_edition(item, "setup")


@keyword
def run_test(arg: Cloaked[Item]):
    item = arg.value
    # mostly copied from the middle of `_pytest.runner.runtestprotocol`:
    reports = item.stash[_report_key]
    if reports[0].passed:
        if item.config.getoption(
            "setupshow",
            default=False,  # pyright:ignore[reportArgumentType]
        ):
            show_test_item(item)
        if not item.config.getoption(
            "setuponly",
            default=False,  # pyright:ignore[reportArgumentType]
        ):
            _call_and_report_robot_edition(item, "call")


@keyword
def teardown(arg: Cloaked[Item]):
    item = arg.value
    # mostly copied from the end of `_pytest.runner.runtestprotocol`:
    _call_and_report_robot_edition(item, "teardown", nextitem=item.nextitem)
    cringe_globals._current_item = None  # pyright:ignore[reportPrivateUsage]
