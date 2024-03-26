# contributing

unlike many projects, i try to make mine as easy as possible for other developers to work on by committing IDE config files and using tools such as rye to automate the installation of all the dev dependencies, including python itself, so the steps to get set up are quite straightforward:

## prerequisites

- python (>=3.8)
- vscode (optional)
  - shows inline errors for all linters used in the CI
  - applies formatting fixes on save to prevent formatting errors from occurring in the CI
  - there are tasks configured in the project to make installing dependencies and running tests more convenient

## installation steps

1. clone the repo
2. install [rye](https://rye-up.com/guide/installation/)
3. in the project root directory, run `rye sync`
4. if using vscode, click "Yes" when prompted to use the project venv and when prompted to install the recommended extensions

## tests

since this is a pytest plugin, we have are two types of tests:

- the plugin tests (located in [`./tests/test_python.py`](./tests/test_python.py) and [`./tests/test_robot.py`](./tests/test_robot.py)) - these use pytester to run pytest against the fixture tests
- the "fixture" tests ([`./tests/fixtures`](./tests/fixtures)) - the tests that the plugin tests run and validate the results of

each plugin test is tied to a fixture test by the test name. for example, the following test runs the fixture test at [`./tests/fixtures/test_python/test_one_test_passes.py`](./tests/fixtures/test_python/test_one_test_passes.py):

```py
# ./tests/test_python.py
def test_one_test_passes(pytester_dir: PytesterDir):
    run_and_assert_result(pytester_dir, passed=1)
    assert_log_file_exists(pytester_dir)
```

the `pytester_dir` fixture is an extension of [pytester](https://docs.pytest.org/en/7.1.x/reference/reference.html#pytester) which gets the path to the current test file relative to the `tests` directory (`./test_python.py`) and ties it to a folder in `./tests/fixtures` with the same name (minus the `.py`, ie. `./tests/fixtures/test_python`), then looks for either a python or robot file in that directory with the same name as the test (`test_one_test_passes.py` or `test_one_test_passes.robot`), or a folder if the test requires multiple files.

TL;DR: the test `tests/suite_name.py::test_name` looks in `tests/fixtures/suite_name` for a file called `test_name.py`, `test_name.robot` or a folder called `test_name`, then runs pytest with the robotframework plugin on the tests there
