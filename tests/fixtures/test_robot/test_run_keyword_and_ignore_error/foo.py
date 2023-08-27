from pytest_robotframework import keyword


@keyword
def bar():
    raise Exception
