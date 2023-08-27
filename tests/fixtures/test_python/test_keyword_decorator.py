from pytest_robotframework import keyword


@keyword
def foo():
    """hie"""


def test_docstring():
    foo()
