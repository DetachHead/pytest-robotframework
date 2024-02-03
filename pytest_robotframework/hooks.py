# ideally this would be in _internal so this would go without saying, but i can't figure out any
# other way to get this module to show up in pdoc
"""new hooks defined by the pytest_robotframework plugin. these are not to be imported. see
[the documentation for pytest hook functions](https://docs.pytest.org/en/7.1.x/how-to/writing_hook_functions.html)
for information on how to use them."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest import hookspec

if TYPE_CHECKING:
    from pytest import Session

    from pytest_robotframework._internal.robot_utils import RobotOptions

# these are basically abstract methods, but hooks are defined in this wacky way which isn't
# supported by linters/type checkers:

# https://github.com/pytest-dev/pytest/issues/11300
# pyright:reportReturnType=false
# https://github.com/astral-sh/ruff/issues/7286
# https://github.com/astral-sh/ruff/issues/9803
# ruff: noqa: ARG001, FBT001


@hookspec
def pytest_robot_modify_options(options: RobotOptions, session: Session):
    """modify the arguments passed to robot in-place

    :param options: the arguments to be passed to robot in dict format. for example,
    `{"listener": ["Foo", "Bar"]}`means `--listener Foo --listener Bar`)
    :param session: the pytest `Session` object
    """
