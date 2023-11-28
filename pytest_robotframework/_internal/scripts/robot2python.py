from __future__ import annotations

from ast import (
    Call,
    Constant,
    Expr,
    FunctionDef,
    ImportFrom,
    Module,
    Name,
    alias,
    arg,
    arguments,
    expr,
    parse,
    stmt,
)
from contextlib import contextmanager, nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Iterator, cast

from robot.api import SuiteVisitor, logger
from robot.api.interfaces import (
    ListenerV2,
    StartKeywordAttributes,
    StartSuiteAttributes,
)
from robot.api.parsing import ModelVisitor
from robot.libraries import STDLIBS
from robot.run import RobotFramework
from typer import run
from typing_extensions import override

import pytest_robotframework
from pytest_robotframework._internal.errors import InternalError, UserError
from pytest_robotframework._internal.utils import unparse

if TYPE_CHECKING:
    from types import ModuleType

    from robot import model, result


def _pythonify_name(name: str) -> str:
    return name.lower().replace(" ", "_")


def _pytestify_name(name: str) -> str:
    return f"test_{_pythonify_name(name)}"


def _module_name(module: ModuleType | str) -> str:
    return module if isinstance(module, str) else module.__name__


def _robot_file(suite: model.TestSuite) -> Path | None:
    if suite.source is None:
        raise InternalError(f"ayo whyyo suite aint got no path 💀 ({suite.name})")
    suite_path = Path(suite.source)
    return suite_path if suite_path.suffix == ".robot" else None


class Robot2PythonListener(ListenerV2):
    @override
    def start_keyword(self, name: str, attributes: StartKeywordAttributes):
        super().start_keyword(name, attributes)


class Robot2Python(SuiteVisitor):
    def __init__(self, output_dir: Path) -> None:
        self.modules: dict[Path, Module] = {}
        self.output_dir = output_dir
        self.current_module: Module
        self.statement_stack: list[stmt] = []

    @property
    def context(self) -> stmt:
        return self.statement_stack[-1]

    @contextmanager
    def _stack_frame(self, statement: stmt) -> Iterator[None]:
        self.statement_stack.append(statement)
        try:
            yield
        finally:
            self.statement_stack.pop()

    def _add_import(self, module: ModuleType | str, names: list[str] | None = None):
        module_name = _module_name(module)
        if names is None:
            names = ["*"]
        if [
            expression
            for expression in self.current_module.body
            if isinstance(expression, ImportFrom)
            and expression.module == module_name
            and set(expression.names) & {"*", *names}
        ]:
            return
        self.current_module.body.insert(
            # __future__ imports need to go first
            (0 if module_name == "__future__" else 1),
            ImportFrom(
                module=module_name,
                names=([  # type:ignore[no-any-expr]
                    alias(name=name, asname=None) for name in names
                ]),
                level=0,
            ),
        )

    def _name(self, name: str, *, module: ModuleType | str | None) -> Name:
        if module:
            self._add_import(module, [name])
        return Name(id=name)

    @override
    def start_suite(self, suite: result.TestSuite):
        robot_file = _robot_file(suite)
        if robot_file is None:
            return
        module = Module(
            body=[], type_ignores=[]  # type:ignore[no-any-expr]
        )
        self.current_module = module
        self._add_import("__future__", ["annotations"])
        self.modules[
            self.output_dir
            / (robot_file.parent).relative_to(self.output_dir)
            / f"{_pytestify_name(robot_file.stem)}.py"
        ] = module

    @override
    def end_suite(self, suite: result.TestSuite):
        if _robot_file(suite) is not None:
            del self.current_module

    @override
    def visit_test(self, test: result.TestCase):
        test_function = FunctionDef(
            name=_pytestify_name(test.name),
            args=[],  # type:ignore[no-any-expr]
            decorator_list=[],  # type:ignore[no-any-expr]
            body=[],  # type:ignore[no-any-expr]
            lineno=-1,
        )
        self.current_module.body.append(test_function)
        with self._stack_frame(test_function):
            super().visit_test(test)

    @override
    # https://github.com/robotframework/robotframework/issues/4940
    def visit_keyword(self, keyword: result.Keyword):  # type:ignore[override]
        if not keyword.name:
            raise UserError("why yo keyword aint got no name")
        strcomputer = "."
        call: expr | None = None

        def create_call(function: str, module: ModuleType | str | None = None) -> Call:
            return Call(
                func=self._name(function, module=module),
                args=[
                    # CRINGE: i cbf figureing out how to properly convert robot variables for now so
                    # just turn them all into fstrings in the jankiest way possible
                    parse(f"f{arg.replace('${{', '{{')!r}").body[0]
                    for arg in keyword.args  # type:ignore[no-any-expr]
                ],
                # TODO
                keywords=[],  # type:ignore[no-any-expr]
            )

        library_name, _, keyword_name = keyword.name.rpartition(strcomputer)
        function_name = _pythonify_name(keyword_name)
        module_name: str | None = None
        if strcomputer in keyword.name:
            # if there's a . that means it was imported from some other module:
            if library_name in STDLIBS:
                if function_name == "no_operation":
                    call = Constant(value=...)
                elif function_name == "log":
                    call = create_call("info", logger)
                module_name = f"robot.libraries.{library_name}"
            else:
                module_name = _pythonify_name(library_name)
            keyword_function = None
        else:
            # otherwise assume it was defined in this robot file
            keyword_function = FunctionDef(
                name=_pythonify_name(function_name),
                args=arguments(
                    # TODO: is there a way to get the positional arg names?
                    args=[
                        arg(arg=f"arg{index}")
                        for index, _ in enumerate(
                            keyword.args
                        )  # type:ignore[no-any-expr]
                    ]
                ),
                decorator_list=[
                    self._name("keyword", module=pytest_robotframework)
                ],  # type:ignore[no-any-expr]
                body=[],  # type:ignore[no-any-expr]
                lineno=-1,
            )
            self.current_module.body.insert(
                # insert the keyword before the first test
                next(
                    index
                    for index, statement in enumerate(self.current_module.body)
                    if isinstance(statement, FunctionDef)
                ),
                keyword_function,
            )
        if not call:
            call = create_call(function_name, module_name)
        cast(FunctionDef, self.context).body.append(Expr(call))

        with self._stack_frame(keyword_function) if keyword_function else nullcontext():
            super().visit_keyword(keyword)


def _convert(suite: Path, output: Path) -> dict[Path, str]:
    suite = suite.resolve()
    output = output.resolve()
    robot_2_python = Robot2Python(output)
    # ideally we'd set output and log to None since they aren't used, but theyu're needed for the
    # prerebotmodifier to run:
    with TemporaryDirectory() as output_dir:
        RobotFramework().main(  # type:ignore[no-untyped-call]
            [suite],  # type:ignore[no-any-expr]
            dryrun=True,
            listener=Robot2PythonListener(),
            prerebotmodifier=robot_2_python,
            runemptysuite=True,
            outputdir=output_dir,
            report=None,
            exitonerror=True,
        )
    return {path: unparse(module) for path, module in robot_2_python.modules.items()}


def main():
    def inner(suite: Path, output: Path):
        for path, module_text in _convert(suite, output).items():
            if not path.parent.exists():
                path.parent.mkdir(parents=True)
            path.write_text(module_text)

    run(inner)
