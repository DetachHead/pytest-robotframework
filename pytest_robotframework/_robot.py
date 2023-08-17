from __future__ import annotations

from collections.abc import Iterable
from os import PathLike
from typing import cast

from pytest import Config, File, Item, MarkDecorator, Session, StashKey, mark
from robot import running
from robot.libraries.BuiltIn import BuiltIn
from robot.model import TestSuite
from robot.running.bodyrunner import BodyRunner
from robot.running.context import EXECUTION_CONTEXTS
from typing_extensions import override

from pytest_robotframework._common import (
    original_body_key,
    original_setup_key,
    original_teardown_key,
    test_case_key,
)

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
        self.stash[test_case_key] = robot_test
        for tag in robot_test.tags:
            tag, *args = tag.split(":")
            self.add_marker(cast(MarkDecorator, getattr(mark, tag))(*args))

    @override
    def setup(self):
        setup_keyword = self.stash[original_setup_key]
        if setup_keyword:
            BuiltIn().run_keyword(setup_keyword.name)

    @override
    def runtest(self):
        test = self.stash[test_case_key]
        BodyRunner(
            EXECUTION_CONTEXTS.current,  # type:ignore[no-any-expr]
            templated=bool(test.template),
        ).run(  # type:ignore[no-untyped-call]
            self.stash[original_body_key]
        )

    @override
    def teardown(self):
        teardown_keyword = self.stash[original_teardown_key]
        if teardown_keyword:
            BuiltIn().run_keyword(teardown_keyword.name)

    @override
    def reportinfo(self) -> (PathLike[str] | str, int | None, str):
        return (self.path, self.stash[test_case_key].lineno, self.name)
