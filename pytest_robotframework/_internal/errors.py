from __future__ import annotations


class PytestRobotError(Exception):
    """base class for all errors raised by this plugin"""


class UserError(PytestRobotError):
    """probably your fault"""


class NotSupportedError(PytestRobotError):
    """my fault"""

    def __init__(self, message: str, issue_number: int) -> None:
        super().__init__(
            f"the pytest-robotframework plugindoes not yet support {message}. see"
            f" https://github.com/detachhead/pytest-robotframework/issues/{issue_number}"
        )


class InternalError(PytestRobotError):
    """probably my fault"""

    def __init__(self, message: str) -> None:
        super().__init__(
            "something went wrong with the pytest-robotframework plugin. please raise"
            " an issue at https://github.com/detachhead/pytest-robotframework with the"
            f" following information:\n\n{message}"
        )
