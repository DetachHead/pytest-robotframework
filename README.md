# pytest-robotframework

a pytest plugin to run robotframework with tests written in python, so you can use the robot log without the robot language

![](https://github.com/DetachHead/pytest-robotframework/assets/57028336/9caabc2e-450e-4db6-bb63-e149a38d49a2)


## install

not on pypi yet so install it from github for now:
```toml
# pyproject.toml with poetry
[tool.poetry.group.dev.dependencies]
pytest-robotframework = { git = "https://github.com/DetachHead/pytest-robotframework.git", rev = "master" }
```

## usage

pytest should automatically find and activate the plugin once you install it, so all you should have to do is write tests with pytest like you would normally:

```py
# you can use both robot and pytest features
from robot.api import logger
from pytest import Cache

from pytest_robotframework import keyword

@keyword  # make this function show as a keyword in the robot log
def foo():
    ...


def test_foo(cache: Cache):
    foo()
```

### setup/teardown and other hooks

to define a function that runs for each test at setup or teardown, create a `conftest.py` with a `pytest_runtest_setup` and/or `pytest_runtest_teardown` function:

```py
# ./tests/conftest.py
def pytest_runtest_setup():
    log_in()
```
```py
# ./tests/test_suite.py
def test_something():
    """i am logged in now"""
```

for more information, see [writing hook functions](https://docs.pytest.org/en/7.1.x/how-to/writing_hook_functions.html). pretty much every pytest hook should work with this plugin
but i haven't tested them all. please raise an issue if you find one that's broken.

### tags/markers

pytest markers are converted to tags in the robot log:

```py
from pytest import mark

@mark.slow
def test_blazingly_fast_sorting_algorithm():
    [1,2,3].sort()
```

![](https://github.com/DetachHead/pytest-robotframework/assets/57028336/f25ee4bd-2f10-42b4-bdef-18a22379bd0d)
