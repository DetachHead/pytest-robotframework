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
    expr,
    stmt,
)
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, cast

from robot.api import SuiteVisitor, logger
from robot.run import RobotFramework
from typer import run
from typing_extensions import override

from pytest_robotframework._internal.errors import InternalError, UserError
from pytest_robotframework._internal.utils import unparse

if TYPE_CHECKING:
    from types import ModuleType

    from robot import model


def _pythonify_name(name: str) -> str:
    return name.lower().replace(" ", "_")


def _pytestify_name(name: str) -> str:
    return f"test_{_pythonify_name(name)}"


def _robot_file(suite: model.TestSuite) -> Path | None:
    if suite.source is None:
        raise InternalError(f"ayo whyyo suite aint got no path 💀 ({suite.name})")
    suite_path = Path(suite.source)
    return suite_path if suite_path.suffix == ".robot" else None


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

    def _add_import(self, module: ModuleType, names: list[str]):
        # insert it at the top of the file but not before the `__future__` import
        self.current_module.body.insert(
            1,
            ImportFrom(
                module=module.__name__,
                names=[alias(name=name) for name in names],  # type:ignore[no-any-expr]
            ),
        )

    @override
    def start_suite(self, suite: model.TestSuite):
        robot_file = _robot_file(suite)
        if robot_file is None:
            return
        module = Module(
            body=[
                ImportFrom(
                    module="__future__",
                    names=[alias(name="annotations")],  # type:ignore[no-any-expr]
                )
            ],
            type_ignores=[],  # type:ignore[no-any-expr]
        )
        self.current_module = module
        self.modules[
            # cringe
            Path(
                str(robot_file.parent.resolve()).replace(
                    str(Path.cwd()), str(self.output_dir)
                )
            )
            / f"{_pytestify_name(robot_file.stem)}.py"
        ] = module

    @override
    def end_suite(self, suite: model.TestSuite):
        # make sure no tests are actually executed once this is done
        suite.tests.clear()  # type:ignore[no-untyped-call]
        if _robot_file(suite) is not None:
            del self.current_module

    @override
    def visit_test(self, test: model.TestCase):
        function = FunctionDef(
            name=_pytestify_name(test.name),
            args=[],  # type:ignore[no-any-expr]
            decorator_list=[],  # type:ignore[no-any-expr]
            body=[],  # type:ignore[no-any-expr]
            lineno=-1,
        )
        self.current_module.body.append(function)
        with self._stack_frame(function):
            super().visit_test(test)

    # eventually this will add imports to self.current_module
    def _resolve_call(self, keyword: model.Keyword) -> expr:
        if not keyword.name:
            raise UserError("why yo keyword aint got no name")
        python_name = _pythonify_name(keyword.name)

        def create_call(module: ModuleType, function: str) -> Call:
            self._add_import(module, [function])
            return Call(
                func=Name(id=function),
                args=[
                    Constant(value=arg)
                    for arg in keyword.args  # type:ignore[no-any-expr]
                ],
                keywords=[],  # type:ignore[no-any-expr]
            )

        if python_name == "no_operation":
            return Constant(value=...)
        if python_name == "log":
            return create_call(logger, "info")
        return Call(
            func=Name(id="run_keyword"),
            args=[
                Constant(value=keyword.name),
                *(
                    Constant(value=arg)
                    for arg in keyword.args  # type:ignore[no-any-expr]
                ),
            ],
            keywords=[],  # type:ignore[no-any-expr]
        )

    @override
    def visit_keyword(self, keyword: model.Keyword):
        function = cast(FunctionDef, self.current_module.body[-1])
        function.body.append(Expr(self._resolve_call(keyword)))
        with self._stack_frame(function):
            super().visit_keyword(keyword)


def _convert(suite: Path, output: Path) -> dict[Path, str]:
    robot_2_python = Robot2Python(output)
    RobotFramework().main(  # type:ignore[no-untyped-call]
        [suite],  # type:ignore[no-any-expr]
        prerunmodifier=robot_2_python,
        runemptysuite=True,
    )
    return {path: unparse(module) for path, module in robot_2_python.modules.items()}


def main(suite: Path, output: Path):
    for path, module_text in _convert(suite, output).items():
        if not path.parent.exists():
            path.parent.mkdir(parents=True)
        path.write_text(module_text)


if __name__ == "__main__":
    run(main)
