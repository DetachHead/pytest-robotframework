<!-- hidden attributes used on elements we only want to hide on the docs site, since they're ignored by github's markdown viewer -->

<h1 hidden>pytest-robotframework</h1>

`pytest-robotframework` is a pytest plugin that creates robotframework reports for tests written
in python and allows you to run robotframework tests with pytest.

![image](https://github.com/DetachHead/pytest-robotframework/assets/57028336/bf0e787c-6343-4ad1-89ff-44b93e17f7f5)

# install

[![Stable Version](https://img.shields.io/pypi/v/pytest-robotframework?color=blue)](https://pypi.org/project/pytest-robotframework/)
[![Conda Version](https://img.shields.io/conda/vn/conda-forge/pytest-robotframework.svg)](https://anaconda.org/conda-forge/pytest-robotframework)

pytest should automatically find and activate the plugin once you install it.

<h1 hidden>API documentation</h1>

<b hidden><a href="https://detachhead.github.io/pytest-robotframework/pytest_robotframework.html#api">click here</a></b>

# features

## write robot tests in python

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

## run `.robot` tests

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
# test_foo.py
from pytest import mark

@keyword
def foo():
    logger.info("ran setup")

@fixture(autouse=True)
def setup():
    foo()

@mark.asdf
@mark.key("value")
def test_bar():
    ...
```

## setup/teardown

in pytest, setups and teardowns are defined using fixtures:

```py
from pytest import fixture
from robot.api import logger

@fixture
def user():
    logger.info("logging in")
    user = ...
    yield user
    logger.info("logging off")

def test_something(user):
    ...
```

under the hood, pytest calls the fixture setup/teardown code as part of the `pytest_runtest_setup` and and `pytest_runtest_teardown` hooks, which appear in the robot log like so:

![image](https://github.com/DetachHead/pytest-robotframework/assets/57028336/5583883e-c9a5-47a0-8796-63418973909d)

for more information, see the pytest documentation for [fixtures](https://docs.pytest.org/en/6.2.x/fixture.html) and [hook functions](https://docs.pytest.org/en/7.1.x/how-to/writing_hook_functions.html).

## tags/markers

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

## robot suite variables

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

## running tests in parallel

running tests in parallel using [pytest-xdist](https://pytest-xdist.readthedocs.io/en/stable/) is supported. when running with xdist, pytest-robotframework will run separate instances of robot for each test, then merge the robot output files together automatically using rebot.

# config

pass `--capture=no` to make `logger.console` work properly.

since this is a pytest plugin, you should avoid using robot options that have pytest equivalents:

| instead of...                           | use...                                | notes                                                                                                                                                   |
| :-------------------------------------- | :------------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `robot --include tag_name`              | `pytest -m tag_name`                  |                                                                                                                                                         |
| `robot --exclude tag_name`              | `pytest -m not tag_name`              |                                                                                                                                                         |
| `robot --skip tag_name`                 | `pytest -m "not tag_name"`            |                                                                                                                                                         |
| `robot --test "test name" ./test.robot` | `pytest ./test.robot::"Test Name"`    |                                                                                                                                                         |
| `robot --suite "suite name" ./folder`   | `pytest ./folder`                     |                                                                                                                                                         |
| `robot --dryrun`                        | `pytest --collect-only`               | not exactly the same. you should use [a type checker](https://github.com/kotlinisland/basedmypy) on your python tests as a replacement for robot dryrun |
| `robot --exitonfailure`                 | `pytest --maxfail=1`                  |                                                                                                                                                         |
| `robot --rerunfailed`                   | `pytest --lf`                         |                                                                                                                                                         |
| `robot --runemptysuite`                 | `pytest --suppress-no-test-exit-code` | requires the [pytest-custom-exit-code](https://pypi.org/project/pytest-custom-exit-code/) plugin                                                        |
| `robot --help`                          | `pytest --help`                       | all supported robot options will be listed in the `robotframework` section                                                                              |

## specifying robot options directlty

there are multiple ways you can specify the robot arguments directly. however, arguments that have pytest equivalents cannot be set with robot as they would cause the plugin to behave incorrectly.

### pytest cli arguments

most robot cli arguments can be passed to pytest by prefixing the argument names with `--robot-`. for example, here's how to change the log level:

#### before

```
robot --loglevel DEBUG:INFO foo.robot
```

#### after

```
pytest --robot-loglevel DEBUG:INFO test_foo.py
```

you can see a complete list of the available arguments using the `pytest --help` command. any robot arguments not present in that list are not supported because they are replaced by a pytest equivalent ([see above](#config)).

### `pytest_robot_modify_options` hook

you can specify a `pytest_robot_modify_options` hook in your `conftest.py` to programmatically modify the arguments. see the [pytest_robotframework.hooks](http://detachhead.github.io/pytest-robotframework/pytest_robotframework/hooks.html#pytest_robot_modify_options) documentation for more information.

```py
from pytest_robotframework import RobotOptions
from robot.api.interfaces import ListenerV3

class Foo(ListenerV3):
    ...

def pytest_robot_modify_options(options: RobotOptions, session: Session) -> None:
    if not session.config.option.collectonly:
        options["loglevel"] = "DEBUG:INFO"
        options["listener"].append(Foo()) # you can specify instances as listeners, prerebotmodifiers, etc.
```

note that not all arguments that the plugin passes to robot will be present in the `args` list. arguments required for the plugin to function (eg. the plugin's listeners and prerunmodifiers) cannot be viewed or modified with this hook

### `ROBOT_OPTIONS` environment variable

```
ROBOT_OPTIONS="-d results --listener foo.Foo"
```

## enabling pytest assertions in the robot log

by default, only failed assertions will appear in the log. to make passed assertions show up, you'll have to add `enable_assertion_pass_hook = true` to your pytest ini options:

```toml
# pyproject.toml
[tool.pytest.ini_options]
enable_assertion_pass_hook = true
```

![image](https://github.com/DetachHead/pytest-robotframework/assets/57028336/c2525ccf-c1c6-4c06-be79-c36fefd3bed4)

### hiding non-user facing assertions

you may have existing `assert` statements in your codebase that are not intended to be part of your tests (eg. for narrowing types/validating input data) and don't want them to show up in the robot log. there are two ways you can can hide individual `assert` statements from the log:

```py
from pytest_robotframework import AssertOptions, hide_asserts_from_robot_log

def test_foo():
    # hide a single passing `assert` statement:
    assert foo == bar, AssertOptions(log_pass=False)

    # hide a group of passing `assert` statements:
    with hide_asserts_from_robot_log():
        assert foo == bar
        assert bar == baz
```

note that failing `assert` statements will still show in the log regardless.

you can also run pytest with the `--no-assertions-in-robot-log` argument to disable `assert` statements in the robot log by default, then use `AssertOptions` to explicitly enable individual `assert` statements:

```py
from pytest_robotframework import AssertOptions

def test_foo():
    assert "foo" == "bar" # hidden from the robot log (when run with --no-assertions-in-robot-log)
    assert "bar" == "baz", AssertOptions(log_pass=True) # not hidden
```

### customizing assertions

pytest-robotframework allows you to customize the message for the `assert` keyword which appears on both passing and failing assertions:

```py
assert 1 == 1  # no custom description
assert 1 == 1, AssertOptions(description="custom description")
```

![image](https://github.com/DetachHead/pytest-robotframework/assets/57028336/582f3589-0ba2-469d-916d-8945e4feffbb)

you can still pass a custom message to be displayed only when your assertion fails:

```py
assert 1 == 2, "the values did not match"
```

however if you want to specify both a custom description and a failure message, you can use the `fail_message` argument:

```py
assert 1 == 2, "failure message"
assert 1 == 2, AssertOptions(description="checking values", fail_message="failure message")
```

![image](https://github.com/DetachHead/pytest-robotframework/assets/57028336/5bae04a0-0545-4df8-9637-59f8f1ef2f04)

note that `enable_assertion_pass_hook` pytest option needs to be enabled for this to work.

# limitations with tests written in python

there are some limitations when writing robotframework tests in python. pytest-robotframework includes solutions for these issues.

## making keywords show in the robot log

by default when writing tests in python, the only keywords that you'll see in the robot log are `Setup`, `Run Test` and `Teardown`. this is because robot is not capable of recognizing keywords called outside of robot code. (see [this issue](https://github.com/robotframework/robotframework/issues/4252))

this plugin has several workarounds for the problem:

### `@keyword` decorator

if you want a function you wrote to show up as a keyword in the log, decorate it with the `pytest_robotframework.keyword` instead of `robot.api.deco.keyword`

```py
from pytest_robotframework import keyword

@keyword
def foo():
    ...
```

### pytest functions are patched by the plugin

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

## continuable failures don't work

keywords that raise [`ContinuableFailure`](https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#continuable-failures) don't work properly when called from python code. this includes builtin keywords such as `Run Keyword And Continue On Failure`.

use `pytest.raises` for expected failures instead:

```py
from pytest import raises

with raises(SomeException):
    some_keyword_that_fails()
```

or if the exception is conditionally raised, use a `try`/`except` statement like you would in regular python code:

```py
try:
    some_keyword_that_fails()
except SomeException:
    ... # ignore the exception, or re-raise it later
```

the keyword will still show as failed in the log (as long as it's decorated with `pytest_robotframework.keyword`), but it won't effect the status of the test unless the exception is re-raised.

### why?

robotframework introduced `TRY`/`EXCEPT` statements in version 5.0, which they [now recommend using](https://robotframework.org/robotframework/latest/RobotFrameworkUserGuide.html#other-ways-to-handle-errors) instead of the old `Run Keyword And Ignore Error`/`Run Keyword And Expect Error` keywords.

however `TRY`/`EXCEPT` behaves differently to its python equivalent, as it allows for errors that do not actually raise an exception to be caught:

```robot
*** Test Cases ***
Foo
    TRY
        Run Keyword And Continue On Failure    Fail
        Log    this is executed
    EXCEPT
        Log    and so is this
    END
```

this means that if control flows like `Run Keyword And Continue On Failure` were supported, its failures would be impossible to catch:

```py
from robot.api.logger import info
from robot.libraries.BuiltIn import BuiltIn

try:
    BuiltIn().run_keyword_and_continue_on_failure("fail")
    info("this is executed because an exception was not actually raised")
except:
    info("this is NOT executed, but the test will still fail")
```

# IDE integration

## vscode

vscode's builtin python plugin should discover both your python and robot tests by default, and show run buttons next to them:

![image](https://github.com/DetachHead/pytest-robotframework/assets/57028336/d81278cc-1574-4360-be3c-29805b47dec6)
![image](https://github.com/DetachHead/pytest-robotframework/assets/57028336/cce2fc08-806f-4b0e-85b9-42be677871ab)

### running `.robot` tests

if you still intend to use `.robot` files with pytest-robotframework, we recommend using the [robotcode](https://github.com/d-biehl/robotcode) extension and setting `robotcode.testExplorer.enabled` to `false` in `.vscode/settings.json`. this will prevent the tests from being duplicated in the test explorer.

## pycharm

pycharm currently does not support pytest plugins for non-python files. see [this issue](https://youtrack.jetbrains.com/issue/PY-63110/use-pytest-collect-only-to-collect-pytest-tests)

# compatibility

| dependency     | version range | comments                                                                                                                                                                                                   |
| :------------- | :------------ | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| python         | `>=3.9,<4.0`  | all versions of python will be supported until their end-of-life as described [here](https://devguide.python.org/versions/)                                                                                |
| robotframework | `>=6.1,<8.0`  | i will try to support at least the two most recent major versions. robot 6.0 is not supported as the parser API that the plugin relies on to support tests written in python was introduced in version 6.1 |
| pytest         | `>=7.0,<9.0`  | may work on other versions, but things may break since this plugin relies on some internal pytest modules                                                                                                  |
