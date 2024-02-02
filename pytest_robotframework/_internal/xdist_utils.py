from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pytest import Session


def get_xdist():
    try:
        # xdist may not be installed
        import xdist  # noqa: PLC0415
    except ModuleNotFoundError:
        return None
    return xdist


def is_xdist_master(session: Session):
    return session.config.option.numprocesses is not None


def worker_id(session: Session) -> str | None:
    xdist = get_xdist()
    if xdist is None:
        return None
    result = cast(
        str,
        xdist.get_xdist_worker_id(session),  # pyright:ignore[reportUnknownMemberType]
    )
    return None if result == "master" else result


def is_xdist_worker(session: Session) -> bool:
    """checks whether the test is running in xdist mode (`-n` argument), since we need special
    handling to support it"""
    return worker_id(session) is not None


def is_xdist(session: Session) -> bool:
    return is_xdist_master(session) or is_xdist_worker(session)
