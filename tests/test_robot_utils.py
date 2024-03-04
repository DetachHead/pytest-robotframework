from __future__ import annotations

from pytest_robotframework._internal.robot.utils import merge_robot_options


def test_merge_robot_options():
    assert merge_robot_options({"a": "b", "c": "d"}, {"c": "e"}) == {"a": "b", "c": "e"}


def test_merge_robot_options_list():
    assert merge_robot_options({"a": ["b"], "c": "d"}, {"a": ["e"]}) == {"a": ["b", "e"], "c": "d"}


def test_merge_robot_options_other_side():
    assert merge_robot_options({"c": "e"}, {"a": "b", "c": "d"}) == {"a": "b", "c": "d"}


def test_merge_robot_options_list_on_one_side():
    assert merge_robot_options({"a": ["b"], "c": "d"}, {"c": "e"}) == {"a": ["b"], "c": "e"}


def test_merge_robot_options_list_left_side_is_none():
    assert merge_robot_options({"a": None, "c": "d"}, {"a": ["e"]}) == {"a": ["e"], "c": "d"}


def test_merge_robot_options_list_right_side_is_none():
    assert merge_robot_options({"a": ["b"], "c": "d"}, {"a": None}) == {"a": None, "c": "d"}


def test_merge_robot_options_3_dicts():
    assert merge_robot_options({"a": "b", "c": "d"}, {"c": "e"}, {"a": "f"}) == {"a": "f", "c": "e"}


def test_merge_robot_options_list_3_dicts():
    assert merge_robot_options({"a": ["b"], "c": "d"}, {"a": ["e"]}, {"a": ["f"]}) == {
        "a": ["b", "e", "f"],
        "c": "d",
    }
