from robot.api import logger


def pytest_runtest_teardown():
    logger.info(2)  # type:ignore[no-untyped-call]
