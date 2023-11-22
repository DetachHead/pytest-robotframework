from __future__ import annotations

from ast import Call, Constant, Expr, FunctionDef, Module, Name, stmt
from pathlib import Path
from typing import TYPE_CHECKING, cast

from robot.api import SuiteVisitor
from robot.run import RobotFramework
from typer import run
from typing_extensions import override

from pytest_robotframework._internal.errors import InternalError, UserError
from pytest_robotframework._internal.utils import unparse

if TYPE_CHECKING:
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
        self.module_stack: list[Module] = []
        self.statement_stack: list[stmt] = []

    @override
    def start_suite(self, suite: model.TestSuite):
        robot_file = _robot_file(suite)
        if robot_file is None:
            return
        module = Module(
            body=[], type_ignores=[]  # type:ignore[no-any-expr]
        )
        self.module_stack.append(module)
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
            self.module_stack.pop()

    @override
    def start_test(self, test: model.TestCase):
        function = FunctionDef(
            name=_pytestify_name(test.name),
            args=[],  # type:ignore[no-any-expr]
            decorator_list=[],  # type:ignore[no-any-expr]
            body=[],  # type:ignore[no-any-expr]
            lineno=-1,
        )
        self.statement_stack.append(function)
        self.module_stack[-1].body.append(function)

    @override
    def end_test(self, test: model.TestCase):
        self.statement_stack.pop()

    @override
    def start_keyword(self, keyword: model.Keyword):
        function = cast(FunctionDef, self.module_stack[-1].body[-1])
        self.statement_stack.append(function)
        if not keyword.name:
            raise UserError("why yo keyword aint got no name")
        function.body.append(
            Expr(
                Call(
                    func=Name(id=_pythonify_name(keyword.name)),
                    args=[
                        Constant(value=arg)
                        for arg in keyword.args  # type:ignore[no-any-expr]
                    ],
                    keywords=[],  # type:ignore[no-any-expr]
                )
            )
        )

    @override
    def end_keyword(self, keyword: model.Keyword):
        self.statement_stack.pop()


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
