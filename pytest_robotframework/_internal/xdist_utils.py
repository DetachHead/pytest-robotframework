from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import Item, Session


def is_xdist_master(session: Session):
    return session.config.option.numprocesses is not None


def worker_id() -> str | None:
    return os.environ.get("PYTEST_XDIST_WORKER", None)


def is_xdist_worker() -> bool:
    """checks whether the test is running in xdist mode (`-n` argument), since we need special
    handling to support it"""
    return worker_id() is not None


def is_xdist(session: Session) -> bool:
    return is_xdist_master(session) or is_xdist_worker()


@dataclass
class JobInfo:
    """info about the current job if running with pytest-xdist"""

    item: Item
    nextitem: Item | None
    temp_dir: Path
