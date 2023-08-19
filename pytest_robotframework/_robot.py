from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, cast

from pytest import Config, File, Item, MarkDecorator, Session, StashKey, mark, skip
from robot.api import SuiteVisitor
from robot.errors import ExecutionFailed
from robot.libraries.BuiltIn import BuiltIn
from robot.model import TestSuite
from robot.running.bodyrunner import BodyRunner
from robot.running.context import EXECUTION_CONTEXTS, _ExecutionContext
from typing_extensions import override

from pytest_robotframework._common import (
    get_item_from_robot_test,
    original_body_key,
    original_setup_key,
    original_teardown_key,
    running_test_case_key,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from os import PathLike

    from robot import running

collected_robot_suite_key = StashKey[TestSuite]()


class RobotFile(File):
    @override
    def collect(self) -> Iterable[Item]:
        for test in self.session.stash[collected_robot_suite_key].all_tests:
            if self.path == test.source:
                yield RobotItem.from_parent(  # type:ignore[no-untyped-call,no-any-expr]
                    self, name=test.name, robot_test=test
                )


class RobotItem(Item):
    def __init__(
        self,
        *,
        robot_test: running.TestCase,
        name: str,
        parent: RobotItem | None = None,
        config: Config | None = None,
        session: Session | None = None,
        nodeid: str | None = None,
        **kwargs: object,
    ):
        super().__init__(
            name=name,
            parent=parent,
            config=config,
            session=session,
            nodeid=nodeid,
            **kwargs,
        )
        # ideally this would just be stored on a normal attribute but we want a consistent way
        # of accessing the robot test from both `RobotItem`s and regular `Item`s
        self.stash[running_test_case_key] = robot_test
        for tag in robot_test.tags:
            tag, *args = tag.split(":")
            self.add_marker(cast(MarkDecorator, getattr(mark, tag))(*args))

    @contextmanager
    def _check_skipped(self) -> Iterator[None]:
        """since robot and pytest skips are different, we need to catch robot skips and convert them to pytest skips"""
        try:
            yield
        except ExecutionFailed as e:
            if e.status == "SKIP":  # type:ignore[no-any-expr]
                skip(e.message)  # type:ignore[no-any-expr]
            raise

    @override
    def setup(self):
        setup_keyword = self.stash[original_setup_key]
        if setup_keyword:
            with self._check_skipped():
                BuiltIn().run_keyword(setup_keyword.name)

    @override
    def runtest(self):
        test = self.stash[running_test_case_key]
        context = cast(_ExecutionContext, EXECUTION_CONTEXTS.current)
        with self._check_skipped():
            BodyRunner(
                context=context, templated=bool(test.template)
            ).run(  # type:ignore[no-untyped-call]
                self.stash[original_body_key]
            )

    @override
    def teardown(self):
        teardown_keyword = self.stash[original_teardown_key]
        if teardown_keyword:
            with self._check_skipped():
                BuiltIn().run_keyword(teardown_keyword.name)

    @override
    def reportinfo(self) -> (PathLike[str] | str, int | None, str):
        return (self.path, self.stash[running_test_case_key].lineno, self.name)


class CollectedTestsFilterer(SuiteVisitor):
    """filters out any tests/suites from the collected robot tests that are not included in the collected
    pytest tests"""

    def __init__(self, session: Session):
        self.session = session

    @override
    def start_suite(self, suite: running.TestSuite):
        # need to copy when iterating since we are removing items from the original
        for test in suite.tests[:]:
            item = get_item_from_robot_test(self.session, test)
            if not item:
                # happens when running .robot tests that were filtered out by pytest
                suite.tests.remove(test)
                continue

    @override
    def end_suite(self, suite: running.TestSuite):
        """Remove suites that are empty after removing tests."""
        suite.suites = [s for s in suite.suites if s.test_count > 0]
