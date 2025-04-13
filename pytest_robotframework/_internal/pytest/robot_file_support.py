"""classes for extending pytest to be able to collect `.robot` files"""

from __future__ import annotations

import dataclasses
from contextlib import contextmanager
from typing import TYPE_CHECKING, Callable, cast, final

from _pytest._code.code import ReprFileLocation, TerminalRepr
from pytest import Config, ExceptionInfo, File, Item, MarkDecorator, Session, StashKey, mark, skip
from robot import model
from robot.errors import ExecutionFailures, ExecutionStatus, RobotError
from robot.libraries.BuiltIn import BuiltIn
from robot.running.bodyrunner import BodyRunner
from robot.running.model import Body
from robot.running.statusreporter import StatusReporter
from typing_extensions import Concatenate, override

from pytest_robotframework._internal.errors import InternalError
from pytest_robotframework._internal.robot.utils import (
    ModelTestCase,
    execution_context,
    get_arg_with_type,
    robot_6,
    running_test_case_key,
)
from pytest_robotframework._internal.utils import patch_method

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from os import PathLike

    # this type only exists in pytest 8.3+ so it should not be imported at runtime to maintain
    # compatibility with older versions
    from _pytest._code.code import TracebackStyle
    from _pytest._io import TerminalWriter
    from basedtyping import P


collected_robot_tests_key = StashKey[list[ModelTestCase]]()
original_setup_key = StashKey[model.Keyword]()
original_body_key = StashKey[Body]()
original_teardown_key = StashKey[model.Keyword]()


@patch_method(StatusReporter)
def _get_failure(  # pyright: ignore[reportUnusedFunction]
    og: Callable[Concatenate[StatusReporter, P], object],
    self: StatusReporter,
    *args: P.args,
    **kwargs: P.kwargs,
):
    # robot discards the original error, so save it explicitly
    result = og(self, *args, **kwargs)
    if result:
        # this function's signature is different depewnding on the robot version, so we just accept
        # any arguments and iterate over them to find the one we need
        result.error = get_arg_with_type(BaseException, args, kwargs)  # pyright: ignore[reportAttributeAccessIssue]
    return result


class RobotFile(File):
    @override
    def collect(self) -> Iterable[Item]:
        for test in self.session.stash[collected_robot_tests_key]:
            if self.path == test.source:
                yield RobotItem.from_parent(  # pyright:ignore[reportUnknownMemberType]
                    self, name=test.name, robot_test=test
                )


@final
# some internal deprecated pytest thing is causing this false positive, but apparently it will be
# removed in the future
class RobotItem(Item):  # pyright:ignore[reportUninitializedInstanceVariable]
    def __init__(
        self,
        *,
        robot_test: ModelTestCase,
        name: str,
        parent: RobotItem | None = None,
        config: Config | None = None,
        session: Session | None = None,
        nodeid: str | None = None,
        **kwargs: object,
    ):
        super().__init__(  # pyright:ignore[reportUnknownMemberType]
            name=name, parent=parent, config=config, session=session, nodeid=nodeid, **kwargs
        )
        self.collected_robot_test: ModelTestCase = robot_test
        """this should only be used to get metadata from the test and not during the runtestloop
        because it'll be outdated by the time the test actually runs if it's running with xdist
        (robot needs to run once for collection and again for the test execution)

        for the `running.TestCase`, use `RobotItem.stash[running_test_case_key]` instead"""

        self.line_number = robot_test.lineno
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
    def _check_execution_status() -> Iterator[None]:
        """
        catches robot execution status exceptions to turn them into their pytest equivalent
        """
        try:
            yield
        except ExecutionStatus as e:
            if e.status == "SKIP":
                skip(e.message)
            if e.status != "PASS":  # pyright:ignore[reportUnnecessaryComparison] type is wrong
                # unlike robot, pytest does not raise a passed exception
                raise

    def _run_keyword(self, keyword: model.Keyword | None):
        if keyword and keyword.name is not None and keyword.name.lower() != "none":
            with self._check_execution_status():
                BuiltIn().run_keyword(keyword.name, *keyword.args)

    @override
    def setup(self):
        self._run_keyword(self.stash[original_setup_key])

    @override
    def runtest(self):
        test = self.stash[running_test_case_key]
        context = execution_context()
        if not context:
            raise InternalError("failed to runtest because no execution context")
        check_skipped = self._check_execution_status()
        if robot_6:
            with check_skipped:
                # pyright is only run when robot 7 is installed
                BodyRunner(  # pyright:ignore[reportCallIssue]
                    context=context, templated=bool(test.template)
                ).run(self.stash[original_body_key])
        else:
            wrapped_body = test.body
            test.body = self.stash[original_body_key]
            try:
                with check_skipped:
                    BodyRunner(context=context, templated=bool(test.template)).run(
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
        return (self.path, None if self.line_number is None else self.line_number - 1, self.name)

    @override
    def repr_failure(
        self, excinfo: ExceptionInfo[BaseException], style: TracebackStyle | None = None
    ) -> str | TerminalRepr:
        if isinstance(excinfo.value, ExecutionFailures):
            error = cast(BaseException, excinfo.value._errors[-1].error)  # pyright: ignore[reportPrivateUsage, reportUnknownMemberType]
            if isinstance(error, RobotError) or not error.__traceback__:
                return RobotToiletRepr(excinfo.value)
            return super().repr_failure(ExceptionInfo[BaseException].from_exception(error), style)
        return super().repr_failure(excinfo, style)


@dataclasses.dataclass(eq=False)
class RobotToiletRepr(TerminalRepr):
    value: object
    reprcrash: ReprFileLocation = dataclasses.field(init=False)

    def __post_init__(self):
        # To support 'short test summary info'
        self.reprcrash = ReprFileLocation("", -1, str(self.value))

    @override
    def toterminal(self, tw: TerminalWriter):
        tw.line(f"E   {self.value}", red=True, bold=True)
