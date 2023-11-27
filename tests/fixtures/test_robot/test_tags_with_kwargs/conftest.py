from pytest_robotframework._internal.pytest_robot_items import RobotItem


def pytest_runtest_setup(item: RobotItem):
    assert item.name == "Foo"
    marker_names = ["m1", "m2"]
    marker_kwargs = [{"foo": "1", "baz": "false"}, {"bar": "foo", "qux": "7"}]
    for i, marker in enumerate(item.iter_markers()):
        assert marker.name == marker_names[i]
        assert marker.kwargs == marker_kwargs[i]  # type: ignore[no-any-expr]
