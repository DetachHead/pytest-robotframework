from __future__ import annotations


def pytest_robot_modify_args(args: list[str]):
    args.extend(["-v", "foo:bar"])
