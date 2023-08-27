from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, cast

from pytest import Config, File, Item, MarkDecorator, Session, mark, skip
from robot.errors import ExecutionFailed
from robot.libraries.BuiltIn import BuiltIn
from robot.running.bodyrunner import BodyRunner
from robot.running.context import (  # pylint:disable=import-private-name
    EXECUTION_CONTEXTS,
    _ExecutionContext,
)
from typing_extensions import override

from pytest_robotframework._common import (
    collected_robot_suite_key,
    original_body_key,
    original_setup_key,
    original_teardown_key,
    running_test_case_key,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from os import PathLike

    from robot import running


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
        # ideally this would only be stored on a normal attribute but we want a consistent way
        # of accessing the robot test from both `RobotItem`s and regular `Item`s
        self.stash[running_test_case_key] = robot_test
        self.robot_test = robot_test
        for tag in robot_test.tags:
            tag, *args = tag.split(":")
            self.add_marker(cast(MarkDecorator, getattr(mark, tag))(*args))

    @staticmethod
    @contextmanager
    def _check_skipped() -> Iterator[None]:
        """since robot and pytest skips are different, we need to catch robot skips and convert them
        to pytest skips"""
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
