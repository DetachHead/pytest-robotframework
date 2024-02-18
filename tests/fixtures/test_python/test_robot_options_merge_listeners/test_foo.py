from __future__ import annotations

from typing import TYPE_CHECKING

# needed because the import needs to be different after the file is moved
if TYPE_CHECKING:
    from tests.fixtures.test_python.test_robot_options_merge_listeners import Listener
else:
    import Listener


def test_func1():
    assert Listener.called
