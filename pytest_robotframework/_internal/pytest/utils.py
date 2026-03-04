from __future__ import annotations

from typing import Final, cast

from pytest import version_tuple

pytest_version: Final = cast(tuple[int, int, int], version_tuple)
"""
pytest has handiling for "broken installs" in which case the string `"unknown"` is included
in the version tuple. this is an edge case not worth supporting so we just cast it to a tuple of
`int`s instead
"""
