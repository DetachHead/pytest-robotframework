"""
this module only exists because there was nowhere else i could put this stash key without causing
a circular import
"""

from __future__ import annotations

from pytest import StashKey

exception_key = StashKey[BaseException]()
