"""Tests for figure publication outside the user-facing figure directory."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import functions.figure_io as figure_io
from functions.figure_io import (
    STAGING_DIRECTORY,
    atomic_savefig,
    remove_orphaned_figure_staging_files,
)


class _FakeFigure:
    def __init__(self, payload: bytes, *, fail: bool = False) -> None:
        self.payload = payload
        self.fail = fail

    def savefig(self, path: Path, **_: object) -> None:
        path.write_bytes(self.payload)
        if self.fail:
            raise RuntimeError("declared rendering failure")


class FigurePublicationTests(unittest.TestCase):
    def tearDown(self) -> None:
        remove_orphaned_figure_staging_files()

    def test_atomic_publication_replaces_a_complete_target(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            target = Path(directory) / "figure.pdf"
            target.write_bytes(b"old")
            atomic_savefig(_FakeFigure(b"new-complete"), target)
            self.assertEqual(target.read_bytes(), b"new-complete")
            self.assertFalse(STAGING_DIRECTORY.exists())

    def test_fsync_uses_a_write_capable_staging_handle(self) -> None:
        modes: list[str] = []
        original_open = Path.open

        def recording_open(
            path: Path, mode: str = "r", *args: object, **kwargs: object
        ):
            if path.parent == STAGING_DIRECTORY:
                modes.append(mode)
            return original_open(path, mode, *args, **kwargs)

        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            target = Path(directory) / "figure.pdf"
            with patch.object(Path, "open", recording_open):
                atomic_savefig(_FakeFigure(b"portable-complete"), target)

        self.assertIn("r+b", modes)
        self.assertNotIn("rb", modes)
        self.assertFalse(STAGING_DIRECTORY.exists())

    def test_windows_uses_complete_readback_instead_of_crt_commit(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            target = Path(directory) / "figure.pdf"
            with (
                patch.object(figure_io.os, "name", "nt"),
                patch.object(figure_io.os, "fsync") as fsync,
            ):
                atomic_savefig(_FakeFigure(b"windows-complete"), target)

            fsync.assert_not_called()
            self.assertEqual(target.read_bytes(), b"windows-complete")
        self.assertFalse(STAGING_DIRECTORY.exists())

    def test_posix_uses_fsync_instead_of_windows_handle_flush(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            target = Path(directory) / "figure.pdf"
            with (
                patch.object(figure_io.os, "name", "posix"),
                patch.object(figure_io.os, "fsync") as fsync,
            ):
                atomic_savefig(_FakeFigure(b"posix-complete"), target)

        fsync.assert_called_once()
        self.assertFalse(STAGING_DIRECTORY.exists())

    def test_render_failure_preserves_target_and_cleans_staging(self) -> None:
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT) as directory:
            target = Path(directory) / "figure.pdf"
            target.write_bytes(b"accepted")
            with self.assertRaises(RuntimeError):
                atomic_savefig(_FakeFigure(b"partial", fail=True), target)
            self.assertEqual(target.read_bytes(), b"accepted")
            self.assertFalse(STAGING_DIRECTORY.exists())

    def test_cleanup_removes_legacy_and_dedicated_staging(self) -> None:
        legacy = PROJECT_ROOT / "figures" / ".figure-test.tmp.pdf"
        legacy.write_bytes(b"partial")
        STAGING_DIRECTORY.mkdir(exist_ok=True)
        (STAGING_DIRECTORY / "figure-test.tmp.pdf").write_bytes(b"partial")
        remove_orphaned_figure_staging_files()
        self.assertFalse(legacy.exists())
        self.assertFalse(STAGING_DIRECTORY.exists())


if __name__ == "__main__":
    unittest.main()
