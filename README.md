# pytest-robotframework

a pytest plugin to run tests written in python with robotframework tests while generating robot reports for them

![](https://github.com/DetachHead/pytest-robotframework/assets/57028336/9caabc2e-450e-4db6-bb63-e149a38d49a2)

## install

[![Stable Version](https://img.shields.io/pypi/v/pytest-robotframework?color=blue)](https://pypi.org/project/pytest-robotframework/)
[![Conda Version](https://img.shields.io/conda/vn/conda-forge/pytest-robotframework.svg)](https://anaconda.org/conda-forge/pytest-robotframework)

pytest should automatically find and activate the plugin once you install it.

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

@mark.slow  # markers get converted to robot tags
def test_foo():
    foo()
```

### run `.robot` tests

to allow for gradual adoption, the plugin also runs regular robot tests as well:

```robot
*** Settings ***
test setup  foo

*** Test Cases ***
bar
    [Tags]  asdf  key:value
    no operation

*** Keywords ***
foo
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

### listeners and suite visitors

#### listeners

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

or if your listener takes arguments in its constructor, you can call it on the instance instead:

```py
# conftest.py
def pytest_sessionstart():
    listener(Listener("foo"))
```

#### pre-rebot modifiers

just like listeners, you can define [pre-rebot modifiers](https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#programmatic-modification-of-results) using the `pre_rebot_modifier` decorator:

```py
# conftest.py

from pytest_robotframework import pre_rebot_modifier
from robot import model
from robot.api import SuiteVisitor
from robot.utils.misc import printable_name
from typing_extensions import override


@pre_rebot_modifier
class PytestNameChanger(SuiteVisitor):
    """makes pytest test names look like robot test names (eg. `test_do_thing` -> `Do Thing`)"""

    @override
    def start_test(self, test: model.TestCase):
        pytest_prefix = "test_"
        if test.name.startswith(pytest_prefix):
            test.name = printable_name(
                test.name.removeprefix(pytest_prefix), code_style=True
            )
```

or on an instance:

```py
# conftest.py
def pytest_sessionstart():
    listener(PytestNameChanger())
```

#### pre-run modifiers

there is currently no decorator for pre-run modifiers, since they may interfere with the pytest plugin. if you know what you're doing and would like to use a pre-run modifier anyway, you can always [define it in the robot arguments](#specifying-robot-options-directlty).

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
| `robot --prerebotmodifier Foo`                | [`@pre_rebot_modifier` decorator](#pre-rebot-modifiers)                                                                                                                           |
| `robot --dryrun`                              | `pytest --collect-only` (not exactly the same. you should use [a type checker](https://github.com/kotlinisland/basedmypy) on your python tests as a replacement for robot dryrun) |
| `robot --exitonfailure`                       | `pytest --maxfail=1`                                                                                                                                                              |
| `robot --rerunfailed`                         | `pytest --lf`                                                                                                                                                                     |

if the robot option you want to use isn't mentioned here, check the pytest [command line options](https://docs.pytest.org/en/latest/reference/reference.html#command-line-flags) and [ini options](https://docs.pytest.org/en/latest/reference/reference.html#configuration-options) for a complete list of pytest settings as there are probably many missing from this list.

### specifying robot options directlty

there are multiple ways you can specify the robot arguments directly. however, arguments that have pytest equivalents should not be set with robot as they will probably cause the plugin to behave incorrectly.

#### `pytest_robot_modify_args` hook

you can specify a `pytest_robot_modify_args` hook in your `conftest.py` to programmatically modify the arguments

```py
def pytest_robot_modify_args(args: list[str], collect_only: bool, session: Session) -> None:
    if not collect_only:
        args.extend(["--listener", "Foo"])
```

note that not all arguments that the plugin passes to robot will be present in the `args` list. arguments required for the plugin to function (eg. the plugin's listeners and prerunmodifiers) cannot be viewed or modified with this hook

#### `--robotargs` pytest argument

```
pytest --robotargs="-d results --listener foo.Foo"
```

#### `ROBOT_OPTIONS` environment variable

```
ROBOT_OPTIONS="-d results --listener foo.Foo"
```

### enabling pytest assertions in the robot log

by default, only failed assertions will appear in the log. to make passed assertions show up, you'll have to add `enable_assertion_pass_hook = true` to your pytest ini options:

```toml
# pyproject.toml
[tool.pytest.ini_options]
enable_assertion_pass_hook = true
```

![image](https://github.com/DetachHead/pytest-robotframework/assets/57028336/c2525ccf-c1c6-4c06-be79-c36fefd3bed4)

## limitations with python tests

there are several limitations with using robotframework without the language that this plugin includes workarounds for

### making keywords show in the robot log

by default when writing tests in python, the only keywords that you'll see in the robot log are `Setup`, `Run Test` and `Teardown`. this is because robot is not capable of recognizing keywords called outside of robot code. (see [this issue](https://github.com/robotframework/robotframework/issues/4252))

this plugin has several workarounds for the problem:

#### `@keyword` decorator

if you want a function you wrote to show up as a keyword in the log, decorate it with the `pytest_robotframework.keyword` instead of `robot.api.deco.keyword`

```py
from pytest_robotframework import keyword

@keyword
def foo():
    ...
```

#### pytest functions are patched by the plugin

most of the [pytest functions](https://docs.pytest.org/en/7.1.x/reference/reference.html#functions) are patched so that they show as keywords in the robot log

```py
def test_foo():
    with pytest.raises(ZeroDivisionError):
        logger.info(1 / 0)
```

![image](https://github.com/DetachHead/pytest-robotframework/assets/57028336/fc15e9a9-578d-4c5d-bc0f-d5d68591c66c)

#### patching third party functions with `keywordify`

if you want a function from a third party module/robot library to be displayed as a keyword, you can patch it with the `keywordify` function:

```py
# in your conftest.py

from pyest_robotframework import keywordify
import some_module

# patch a function from the module:
keywordify(some_module, "some_function")
# works on classes too:
keywordify(some_module.SomeClass, "some_method")
```

### `run_keyword_and_continue_on_failure` doesn't continue after the failure

some robot keywords such as `run_keyword_and_continue_on_failure` don't work properly when called from python code.

use a `try`/`except` statement to handle expected failures instead:

```py
try:
    some_keyword_that_fails()
except SomeException:
    ... # ignore the exception, or re-raise it later
```

the keyword will still show as failed in the log (as long as it's decorated with `pytest_robotframework.keyword`), but it won't effect the status of the test unless the exception is re-raised

## IDE integration

### vscode

vscode's builtin python plugin should discover both your python and robot tests by default, and show run buttons next to them:

![image](https://github.com/DetachHead/pytest-robotframework/assets/57028336/411233d0-a0d6-4fca-9701-0503b534bd46)

if you use the [robotframework-lsp](https://github.com/robocorp/robotframework-lsp) extension, you'll see duplicated tests on `.robot` files because you have two extensions that can discover them. to fix this, set `robot.testView.enabled` to `false` in vscode's settings.

(note: at the time of writing, this option is not yet in the latest version of the extension, so for now you'll need to install [this build](https://github.com/DetachHead/robotframework-lsp/releases/tag/asdf))

### pycharm

pycharm currently does not support pytest plugins for non-python files. see [this issue](https://youtrack.jetbrains.com/issue/PY-63110/use-pytest-collect-only-to-collect-pytest-tests)
