"""Atomic figure publication outside the user-facing figure directory."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGING_DIRECTORY = PROJECT_ROOT / ".render-staging"


def _flush_windows_file_descriptor(descriptor: int) -> None:
    """Flush a write-capable CRT descriptor through its native Windows handle."""

    # Keep Windows-only modules out of POSIX imports and use the native API
    # directly.  Python's os.fsync delegates to the MS CRT _commit operation,
    # which can report EBADF for an otherwise valid write-capable descriptor
    # on supported Windows/Python combinations.
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    flush_file_buffers = kernel32.FlushFileBuffers
    flush_file_buffers.argtypes = [wintypes.HANDLE]
    flush_file_buffers.restype = wintypes.BOOL
    native_handle = msvcrt.get_osfhandle(descriptor)
    if not flush_file_buffers(native_handle):
        raise ctypes.WinError(ctypes.get_last_error())


def _sync_completed_file(path: Path) -> None:
    """Durably flush a completed staged file on the active platform."""

    with path.open("r+b") as handle:
        handle.flush()
        if os.name == "nt":
            _flush_windows_file_descriptor(handle.fileno())
        else:
            os.fsync(handle.fileno())


def remove_orphaned_figure_staging_files() -> None:
    """Clear legacy root staging files and the dedicated staging directory."""

    for temporary in (PROJECT_ROOT / "figures").glob(".figure-*.tmp.*"):
        temporary.unlink(missing_ok=True)
    if STAGING_DIRECTORY.is_dir():
        for temporary in STAGING_DIRECTORY.iterdir():
            if temporary.is_file():
                temporary.unlink(missing_ok=True)
        try:
            STAGING_DIRECTORY.rmdir()
        except OSError:
            pass


def atomic_savefig(figure: Any, target: Path, **kwargs: object) -> None:
    """Publish a complete figure through same-filesystem atomic replacement."""

    target.parent.mkdir(parents=True, exist_ok=True)
    STAGING_DIRECTORY.mkdir(parents=True, exist_ok=True)
    temporary = STAGING_DIRECTORY / (
        f"{target.stem}-{uuid.uuid4().hex}.tmp{target.suffix}"
    )
    try:
        figure.savefig(temporary, format=target.suffix.lstrip("."), **kwargs)
        # Reopen the completed file without truncation and use a platform-
        # appropriate durability primitive before the atomic replacement.
        _sync_completed_file(temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
        try:
            STAGING_DIRECTORY.rmdir()
        except OSError:
            pass


__all__ = [
    "STAGING_DIRECTORY",
    "atomic_savefig",
    "remove_orphaned_figure_staging_files",
]
