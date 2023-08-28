# pytest-robotframework

a pytest plugin that can run both python and robotframework tests while generating robot reports for them

![](https://github.com/DetachHead/pytest-robotframework/assets/57028336/9caabc2e-450e-4db6-bb63-e149a38d49a2)

## install

pytest should automatically find and activate the plugin once you install it.

```
poetry add pytest-robotframework --group=dev
```

## features

### write robot tests in python

```py
# you can use both robot and pytest features
from robot.api import logger
from pytest import Cache

from pytest_robotframework import keyword

@keyword  # make this function show as a keyword in the robot log
def foo():
    ...

@mark.slow  # gets converted to robot tags
def test_foo(cache: Cache):
    foo()
```

### run `.robot` tests

to allow for gradual adoption, the plugin also runs regular robot tests as well:

```robot
*** Settings ***
test setup  setup

*** Test Cases ***
bar
    [Tags]  asdf  key:value
    no operation

*** Keywords ***
setup
    log  ran setup
```

which is roughly equivalent to the following python code:

```py
# conftest.py
from robot.api import logger
from pytest_robotframework import keyword

def pytest_runtet_setup():
    foo()

@keyword
def foo():
    logger.info("ran setup")
```

```py
# test_foo.py
from pytest import mark

@mark.asdf
@mark.key("value")
def test_bar():
    ...
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

these hooks appear in the log the same way that the a `.robot` file's `Setup` and `Teardown` options in `*** Settings ***` would:

![](https://github.com/DetachHead/pytest-robotframework/assets/57028336/d0b6ee6c-adcd-4f84-9880-9e602c2328f9)

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

markers like `skip`, `skipif` and `parameterize` also work how you'd expect:

```py
from pytest import mark

@mark.parametrize("test_input,expected", [(1, 8), (6, 6)])
def test_eval(test_input: int, expected: int):
    assert test_input == expected
```

![image](https://github.com/DetachHead/pytest-robotframework/assets/57028336/4361295b-5e44-4c9d-b2f3-839e3901b1eb)

### listeners

you can define listeners in your `conftest.py` and decorate them with `@listener` to register them as global listeners:

```py
# conftest.py
from pytest_robotframework import listener
from robot import model, result
from robot.api.interfaces import ListenerV3
from typing_extensions import override

@listener
class Listener(ListenerV3):
    @override
    def start_test(self, data: model.TestCase result: result.TestCase):
        ...
```

### robot suite variables

to set suite-level robot variables, call the `set_variables` function at the top of the test suite:

```py
from robot.libraries.BuiltIn import BuiltIn
from pytest_robotframework import set_variables

set_variables(
    {
        "foo": "bar",
        "baz": ["a", "b"],
    }
)

def test_variables():
    assert BuiltIn().get_variable_value("$foo") == "bar"
```

`set_variables` is equivalent to the `*** Variables ***` section in a `.robot` file. all variables are prefixed with `$`. `@` and `&` are not required since `$` variables can store lists and dicts anyway

## config

since this is a pytest plugin, you should avoid using robot options that have pytest equivalents:

| instead of...                                 | use...                                                                                                                                                                            |
| :-------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `robot --include tag_name`                    | `pytest -m tag_name`                                                                                                                                                              |
| `robot --skip tag_name`                       | `pytest -m "not tag_name"`                                                                                                                                                        |
| `robot --test "test name" path/to/test.robot` | `pytest path/to/test.robot::"Test Name"`                                                                                                                                          |
| `robot --listener Foo`                        | [`@listener` decorator](#listeners)                                                                                                                                               |
| `robot --dryrun`                              | `pytest --collect-only` (not exactly the same. you should use [a type checker](https://github.com/kotlinisland/basedmypy) on your python tests as a replacement for robot dryrun) |
| `robot --exitonfailure`                       | `pytest --maxfail=1`                                                                                                                                                              |
| `robot --rerunfailed`                         | `pytest --lf`                                                                                                                                                                     |

if the robot option you want to use isn't mentioned here, check the pytest [command line options](https://docs.pytest.org/en/latest/reference/reference.html#command-line-flags) and [ini options](https://docs.pytest.org/en/latest/reference/reference.html#configuration-options) for a complete list of pytest settings as there are probably many missing from this list.

#### specifying robot options directlty

you can specify robot CLI arguments directly with the `--robotargs` argument:

```
pytest --robotargs="-d results --listener foo.Foo"
```

or you could use the `ROBOT_OPTIONS` environment variable:

```
ROBOT_OPTIONS="-d results --listener foo.Foo"
```

however, arguments that have pytest equivalents should not be set with robot as they will probably cause the plugin to behave incorrectly.
