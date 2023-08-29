from __future__ import annotations

from types import ModuleType

# callable is not a collection
from typing import Callable, Literal, ParamSpec, cast  # noqa: UP035

from pytest import Function, Item, Session, StashKey, UsageError
from robot import model, result, running
from robot.api import SuiteVisitor
from robot.api.interfaces import ListenerV3
from robot.running.model import Body
from typing_extensions import override

from pytest_robotframework import _robot_library
from pytest_robotframework._errors import InternalError

collected_robot_suite_key = StashKey[model.TestSuite]()
running_test_case_key = StashKey[running.TestCase]()


def get_item_from_robot_test(session: Session, test: running.TestCase) -> Item | None:
    try:
        return next(
            item for item in session.items if item.stash[running_test_case_key] == test
        )
    except StopIteration:
        # the robot test was found but got filtered out by pytest
        return None


_P = ParamSpec("_P")


def create_running_keyword(
    keyword_type: Literal["SETUP", "KEYWORD", "TEARDOWN"],
    fn: Callable[_P, None],
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> running.Keyword:
    """creates a `running.Keyword` for the specified keyword from `_robot_library`"""
    if kwargs:
        raise InternalError(f"kwargs not supported: {kwargs}")
    return running.Keyword(
        name=f"{fn.__module__}.{fn.__name__}",
        # robot says this can only be a str but keywords can take any object when called from
        # python
        args=args,  # type:ignore[arg-type]
        type=keyword_type,
    )


class PytestCollector(SuiteVisitor):
    """
    calls the pytest collection hooks.

    if `collect_only` is `True`, it also removes all suites/tests so that robot doesn't run anything

    if `collect_only` is `False`, it also does the following to prepare the tests for execution:

    - filters out any `.robot` tests/suites that are not included in the collected pytest tests
    - adds the collected `.py` test cases to the robot test suites (with empty bodies. bodies are
    added later by `PytestRuntestProtocolInjector`)
    """

    def __init__(self, session: Session, *, collect_only: bool):
        self.session = session
        self.collect_only = collect_only
        self.collection_error: UsageError | None = None

    @override
    def visit_suite(self, suite: running.TestSuite):
        if not suite.parent:  # only do this once, on the top level suite
            self.session.stash[collected_robot_suite_key] = suite
            try:
                self.session.perform_collect()
            except UsageError as e:
                # if collection fails we still need to clean up the suite (ie. delete all the fake
                # tests), so we defer the error to `end_suite` for the top level suite
                self.collection_error = e
            # create robot test cases for python tests:
            for item in self.session.items:
                if (
                    # don't include RobotItems as .robot files are parsed by robot's default parser
                    not isinstance(item, Function)
                ):
                    continue
                test_case = running.TestCase(
                    name=item.name,
                    doc=cast(Function, item.function).__doc__ or "",
                    tags=[
                        ":".join(
                            [
                                marker.name,
                                *(
                                    str(arg)
                                    for arg in cast(tuple[object, ...], marker.args)
                                ),
                            ]
                        )
                        for marker in item.iter_markers()
                    ],
                )
                test_case.body = Body()
                item.stash[running_test_case_key] = test_case
        if self.collect_only:
            suite.tests.clear()  # type:ignore[no-untyped-call]
            return

        # remove any .robot tests that were filtered out by pytest (and the fake test
        # from `PythonParser`):
        for test in suite.tests[:]:
            if not get_item_from_robot_test(self.session, test):
                # happens when running .robot tests that were filtered out by pytest
                suite.tests.remove(test)

        # add any .py tests that were collected by pytest
        for item in self.session.items:
            if isinstance(item, Function):
                module = cast(ModuleType, item.module)
                if module.__doc__ and not suite.doc:
                    suite.doc = module.__doc__
                if item.path == suite.source:
                    suite.tests.append(item.stash[running_test_case_key])
        super().visit_suite(suite)

    @override
    def end_suite(self, suite: running.TestSuite):
        """Remove suites that are empty after removing tests."""
        suite.suites = [s for s in suite.suites if s.test_count > 0]
        if not suite.parent and self.collection_error:
            raise self.collection_error


original_setup_key = StashKey[model.Keyword]()
original_body_key = StashKey[Body]()
original_teardown_key = StashKey[model.Keyword]()


class PytestRuntestProtocolInjector(SuiteVisitor):
    """injects the hooks from `pytest_runtest_protocol` into the robot test suite. this replaces any
     existing setup/body/teardown with said hooks, which may or may not be an issue depending on
     whether a python or robot test is being run.

    - if running a `.robot` test: the test cases would already have setup/body/teardown keywords, so
    make sure the hooks actually call those keywords (`original_setup_key`, `original_body_key` and
    `original_teardown_key` stashes are used to send the original keywords to the methods on
    `RobotFile`)
    - if running a `.py` test, this is not an issue because the robot test cases are empty (see
    `PythonParser`) and the hook functions already have the actual contents of the tests, because
    they are just plain pytest tests
    """

    def __init__(self, session: Session):
        self.session = session

    @override
    def start_suite(self, suite: running.TestSuite):
        suite.resource.imports.library(
            _robot_library.__name__, alias=_robot_library.__name__
        )
        for test in suite.tests:
            item = get_item_from_robot_test(self.session, test)
            if not item:
                raise InternalError(
                    "this should NEVER happen, `PytestCollector` failed to filter out"
                    f" {test.name}"
                )

            item.stash[original_setup_key] = test.setup
            # TODO: whats this mypy error
            #  https://github.com/DetachHead/pytest-robotframework/issues/36
            test.setup = create_running_keyword(  # type:ignore[assignment]
                "SETUP",
                _robot_library.setup,  # type:ignore[no-any-expr]
                item,
            )

            item.stash[original_body_key] = test.body  # type:ignore[misc]
            test.body = Body(
                items=[
                    create_running_keyword(
                        "KEYWORD",
                        _robot_library.run_test,  # type:ignore[no-any-expr]
                        item,
                    )
                ]
            )

            item.stash[original_teardown_key] = test.teardown
            test.teardown = create_running_keyword(
                "TEARDOWN",
                _robot_library.teardown,  # type:ignore[no-any-expr]
                item,
            )


class PytestRuntestLogListener(ListenerV3):
    """runs the `pytest_runtest_logstart` and `pytest_runtest_logfinish` hooks from
    `pytest_runtest_protocol`. since all the other parts of `_pytest.runner.runtestprotocol` are
    re-implemented in `PytestRuntestProtocolInjector`
    """

    def __init__(self, session: Session):
        self.session = session

    def _get_item(self, data: running.TestCase) -> Item:
        item = get_item_from_robot_test(self.session, data)
        if not item:
            raise InternalError(
                f"failed to find pytest item for robot test: {data.name}"
            )
        return item

    @override
    def start_test(
        self,
        data: running.TestCase,
        result: result.TestCase,  # pylint:disable=redefined-outer-name
    ):
        item = self._get_item(data)
        item.ihook.pytest_runtest_logstart(  # type:ignore[no-any-expr]
            nodeid=item.nodeid, location=item.location
        )

    @override
    def end_test(
        self,
        data: running.TestCase,
        result: result.TestCase,  # pylint:disable=redefined-outer-name
    ):
        item = self._get_item(data)
        item.ihook.pytest_runtest_logfinish(  # type:ignore[no-any-expr]
            nodeid=item.nodeid, location=item.location
        )
