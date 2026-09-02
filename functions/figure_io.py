"""Atomic figure publication outside the user-facing figure directory."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGING_DIRECTORY = PROJECT_ROOT / ".render-staging"


def sync_completed_file(path: Path) -> None:
    """Finalize and verify a completed staged file on the active platform."""

    with path.open("r+b") as handle:
        handle.flush()
        if os.name == "nt":
            # Python's CRT fsync and the native FlushFileBuffers call can fail
            # intermittently for valid files on supported Windows storage.
            # A complete readback catches truncated or unreadable staging bytes
            # before the atomic replacement while file close publishes all
            # Python-buffered writes to the operating system.
            while handle.read(1024 * 1024):
                pass
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
        sync_completed_file(temporary)
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
    "sync_completed_file",
]
