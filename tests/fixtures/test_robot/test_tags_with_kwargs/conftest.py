from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_robotframework._internal.pytest.robot_file_support import RobotItem


def pytest_runtest_setup(item: RobotItem):
    assert item.name == "Foo"
    marker_names = ["m1", "m2"]
    marker_kwargs = [{"foo": "1", "baz": "false"}, {"bar": "foo", "qux": "7"}]
    markers = list(item.iter_markers())
    for marker, marker_name, marker_kwarg in zip(markers, marker_names, marker_kwargs, strict=True):
        assert marker.name == marker_name
        assert marker.kwargs == marker_kwarg
