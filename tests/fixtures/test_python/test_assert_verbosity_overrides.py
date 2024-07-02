from __future__ import annotations

from pytest import fixture

from pytest_robotframework import AssertOptions

# needed for fixtures
# pylint:disable=redefined-outer-name


@fixture
def big_value():
    return list(range(6))


def test_default(big_value: list[int]):
    assert big_value == []


def test_verbose(big_value: list[int]):
    assert big_value == [], AssertOptions(verbosity=2)


def test_set_back_to_default(big_value: list[int]):
    assert big_value == [1]
