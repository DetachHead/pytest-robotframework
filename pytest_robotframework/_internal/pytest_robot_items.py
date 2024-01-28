"""classes for extending pytest to be able to collect `.robot` files"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator, cast

from pytest import Config, File, Item, MarkDecorator, Session, mark, skip
from robot.errors import ExecutionFailed
from robot.libraries.BuiltIn import BuiltIn
from robot.running.bodyrunner import BodyRunner
from typing_extensions import override

from pytest_robotframework._internal.errors import InternalError
from pytest_robotframework._internal.robot_classes import (
    collected_robot_suite_key,
    original_body_key,
    original_setup_key,
    original_teardown_key,
)
from pytest_robotframework._internal.robot_utils import (
    ModelTestCase,
    execution_context,
    robot_6,
    running_test_case_key,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from os import PathLike

    from robot import model, running


class RobotFile(File):
    @override
    def collect(self) -> Iterable[Item]:
        for test in cast(
            Iterator[ModelTestCase],
            # https://github.com/robotframework/robotframework/issues/4940#issuecomment-1817683893
            self.session.stash[  # pyright:ignore[reportUnknownMemberType]
                collected_robot_suite_key
            ].all_tests,
        ):
            if self.path == test.source:
                yield RobotItem.from_parent(  # pyright:ignore[reportUnknownMemberType]
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
        super().__init__(  # pyright:ignore[reportUnknownMemberType]
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
            tag_kwargs: dict[str, str] = {}
            for arg in args:
                try:
                    key, values = arg.split("=")
                except ValueError:
                    break
                tag_kwargs.update({key: values})
            marker = cast(MarkDecorator, getattr(mark, tag))
            if tag_kwargs:
                self.add_marker(marker(**tag_kwargs))
            else:
                self.add_marker(marker(*args))

    @staticmethod
    @contextmanager
    def _check_skipped() -> Iterator[None]:
        """since robot and pytest skips are different, we need to catch robot skips and convert them
        to pytest skips"""
        try:
            yield
        except ExecutionFailed as e:
            if e.status == "SKIP":
                skip(e.message)
            raise

    def _run_keyword(self, keyword: model.Keyword | None):
        if keyword:
            with self._check_skipped():
                BuiltIn().run_keyword(  # pyright:ignore[reportUnknownMemberType]
                    keyword.name, *keyword.args
                )

    @override
    def setup(self):
        self._run_keyword(self.stash[original_setup_key])

    @override
    def runtest(self):
        test = self.robot_test
        context = execution_context()
        if not context:
            raise InternalError("failed to runtest because no execution context")
        check_skipped = self._check_skipped()
        if robot_6:
            with check_skipped:
                # pyright is only run when robot 7 is installed
                BodyRunner(  # pyright:ignore[reportUnknownMemberType,reportCallIssue]
                    context=context, templated=bool(test.template)
                ).run(self.stash[original_body_key])
        else:
            wrapped_body = test.body
            test.body = self.stash[original_body_key]
            try:
                with check_skipped:
                    BodyRunner(  # pyright:ignore[reportUnknownMemberType]
                        context=context, templated=bool(test.template)
                    ).run(
                        data=test,
                        result=context.test,  # pyright:ignore[reportUnknownMemberType]
                    )
            finally:
                test.body = wrapped_body

    @override
    def teardown(self):
        self._run_keyword(self.stash[original_teardown_key])

    @override
    def reportinfo(self) -> tuple[PathLike[str] | str, int | None, str]:
        line_number = self.robot_test.lineno
        return (self.path, None if line_number is None else line_number - 1, self.name)
