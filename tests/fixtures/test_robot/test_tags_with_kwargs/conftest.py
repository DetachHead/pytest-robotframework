from pytest_robotframework._internal.pytest_robot_items import RobotItem


def pytest_runtest_setup(item: RobotItem):
    assert item.name == "Foo"
    marker_names = ["m1", "m2"]
    marker_kwargs = [{"foo": "1", "baz": "false"}, {"bar": "foo", "qux": "7"}]
    for marker, marker_name, marker_kwarg in zip(item.iter_markers(), marker_names, marker_kwargs, strict=True):
        assert marker.name == marker_name
        assert marker.kwargs == marker_kwarg  # type: ignore[no-any-expr]
