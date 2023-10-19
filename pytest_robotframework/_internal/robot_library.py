"""robot library that contains the keywords added by the plugin. this module is imported as a robot
library by `robot_classes.PytestRuntestProtocolInjector`"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Literal, cast

from _pytest._code.code import TerminalRepr
from _pytest.runner import call_and_report, show_test_item
from pytest import Item, StashKey, TestReport
from robot.api.deco import keyword
from robot.libraries.BuiltIn import BuiltIn

from pytest_robotframework._internal import cringe_globals
from pytest_robotframework._internal.errors import InternalError
from pytest_robotframework._internal.pytest_exception_getter import exception_key

if TYPE_CHECKING:
    from pytest_robotframework._internal.robot_utils import Cloaked

_report_key = StashKey[List[TestReport]]()


def _call_and_report_robot_edition(
    item: Item, when: Literal["setup", "call", "teardown"], **kwargs: object
):
    """wrapper for the `call_and_report` function used by `_pytest.runner.runtestprotocol`
    with additional logic to show the result in the robot log"""
    reports: list[TestReport]
    if _report_key in item.stash:
        reports = item.stash[_report_key]
    else:
        reports = []
        item.stash[_report_key] = reports
    report = call_and_report(  # type:ignore[no-untyped-call]
        item, when, log=True, **kwargs
    )
    reports.append(report)
    if report.skipped:
        # empty string means xfail with no reason, None means it was not an xfail
        xfail_reason = (
            cast(str, report.wasxfail) if hasattr(report, "wasxfail") else None
        )
        BuiltIn().skip(  # type:ignore[no-untyped-call]
            # TODO: is there a reliable way to get the reason when skipped by a skip/skipif marker?
            # https://github.com/DetachHead/pytest-robotframework/issues/51
            ""
            if xfail_reason is None
            else ("xfail" + (f": {xfail_reason}" if xfail_reason else ""))
        )
    elif report.failed:
        # make robot show the exception:
        exception = item.stash.get(exception_key, None)
        if exception:
            raise exception
        longrepr = report.longrepr
        if isinstance(longrepr, str):
            # xfail strict and errors caught in our pytest_runtest_makereport hook
            raise Exception(longrepr)
        if isinstance(longrepr, TerminalRepr):
            # errors such as invalid fixture (FixtureLookupErrorRepr)
            raise Exception(str(longrepr))
        raise InternalError(
            f"failed to get exception from failed test ({item=}, {when=}): {longrepr}"
        )


@keyword  # type:ignore[no-any-expr,misc]
def setup(arg: Cloaked[Item]):  # type:ignore[no-any-decorated]
    item = arg.value
    cringe_globals._current_item = item  # noqa: SLF001
    # mostly copied from the start of `_pytest.runner.runtestprotocol`:
    if (
        hasattr(item, "_request")
        and not item._request  # type: ignore[no-any-expr] # noqa: SLF001
    ):
        # This only happens if the item is re-run, as is done by
        # pytest-rerunfailures.
        item._initrequest()  # type: ignore[attr-defined] # noqa: SLF001
    _call_and_report_robot_edition(item, "setup")


@keyword  # type:ignore[no-any-expr,misc]
def run_test(arg: Cloaked[Item]):  # type:ignore[no-any-decorated]
    item = arg.value
    # mostly copied from the middle of `_pytest.runner.runtestprotocol`:
    reports = item.stash[_report_key]
    if reports[0].passed:
        if item.config.getoption(  # type:ignore[no-any-expr,no-untyped-call]
            "setupshow", default=False
        ):
            show_test_item(item)
        if not item.config.getoption(  # type:ignore[no-any-expr,no-untyped-call]
            "setuponly", default=False
        ):
            _call_and_report_robot_edition(item, "call")


@keyword  # type:ignore[no-any-expr,misc]
def teardown(arg: Cloaked[Item]):  # type:ignore[no-any-decorated]
    item = arg.value
    # mostly copied from the end of `_pytest.runner.runtestprotocol`:
    _call_and_report_robot_edition(
        item, "teardown", nextitem=item.nextitem  # type:ignore[no-any-expr]
    )
    cringe_globals._current_item = None  # noqa: SLF001


@keyword  # type:ignore[no-any-expr,misc]
def internal_error(msg: Cloaked[str]):  # type:ignore[no-any-decorated]
    raise InternalError(msg.value)
