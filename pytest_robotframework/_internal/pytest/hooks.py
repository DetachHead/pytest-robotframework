"""
new pytest hooks defined by the `pytest_robotframework` plugin. these are not to be imported. see
[the documentation for pytest hook functions](https://docs.pytest.org/en/stable/how-to/writing_hook_functions.html)
for information on how to use them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import Item, hookspec

if TYPE_CHECKING:
    from pytest import Session

    from pytest_robotframework._internal.robot.utils import RobotOptions

# these are basically abstract methods, but hooks are defined in this wacky way which isn't
# supported by linters/type checkers:

# https://github.com/pytest-dev/pytest/issues/11300
# https://github.com/DetachHead/basedpyright/issues/311
# pyright:reportReturnType=false, reportUnusedParameter=false
# https://github.com/astral-sh/ruff/issues/7286
# ruff: noqa: PLR0917


@hookspec
def pytest_robot_modify_options(options: RobotOptions, session: Session) -> None:
    """
    modify the arguments passed to robot in-place

    example:
    -------
    ```py
    def pytest_robot_modify_options(options: RobotOptions, session: Session) -> None:
    if not session.config.option.collectonly:
        options["loglevel"] = "DEBUG:INFO"
        options["listener"].append(Foo())
    ```

    :param options: the arguments to be passed to robot in dict format. for example,
    `{"listener": ["Foo", "Bar"]}`means `--listener Foo --listener Bar`). you can also specify
    instances of classes to `listener` and `prerebotmodifier`
    :param session: the pytest `Session` object
    """


@hookspec
def pytest_robot_assertion(
    item: Item,
    expression: str,
    fail_message: object,
    line_number: int,
    assertion_error: AssertionError | None,
    explanation: str,
) -> None:
    """
    gets called when an assertion runs. unlike `pytest_assertrepr_compare` and
    `pytest_assertion_pass`, this hook is executed on both passing and failing assertions, and
    allows you to see the second argument passed to `assert` statement

    requires the `enable_assertion_pass_hook` pytest option to be enabled

    !!! warning
        this hook is experimental and relies heavily on patching the internals of pytest. it may
        break, change or be removed at any time. you should only use this hook if you know what
        you're doing

    :param item:
        the currently running item
    :param expression:
        a string containing the the source code of the expression passed to the `assert` statement
    :param fail_message:
        the second argument to the `assert` statement, or `None` if there was none provided
    :param line_number:
        the line number containing the `assert` statement
    :param assertion_error:
        the exception raised if the `assert` statement failed. `None` if the assertion passed.
        you must re-raise the assertion error for the assertion to fail (useful if you want to
        conditionally ignore an assertion error)
    :param explanation:
        pytest's explanation of the result. the format will be different depending on whether the
        assertion passed or failed
    """
