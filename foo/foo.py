from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from pydantic import BaseModel, BeforeValidator as _BeforeValidator


class Foo[T = object]:
    def __init__(self, a: type[object]): ...


@dataclass(frozen=True)
class BeforeValidator(_BeforeValidator):  # ruff:ignore[undocumented-public-class]
    func: Callable[[object], object]


class Bar(BaseModel):  # ruff:ignore[undocumented-public-class]
    bar: Annotated[
        str,
        BeforeValidator(lambda data: {entry["asdf"]: entry["low"] for entry in data}),
    ]


foo = Foo(Bar)
