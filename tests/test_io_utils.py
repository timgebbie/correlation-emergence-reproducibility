"""Tests for atomic publication of tabular and JSON outputs."""

from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from functions.io_utils import (
    OUTPUT_STAGING_DIRECTORY,
    remove_orphaned_output_staging_files,
    write_csv,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]


class _FailingRows:
    def __iter__(self):
        yield {"value": "partial"}
        raise RuntimeError("declared row-generation failure")


class AtomicTabularPublicationTests(unittest.TestCase):
    def tearDown(self) -> None:
        remove_orphaned_output_staging_files()

    def test_csv_replaces_target_only_after_complete_write(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            target = Path(directory) / "values.csv"
            target.write_text("old\n", encoding="utf-8")
            write_csv(target, ["value"], [{"value": 1}, {"value": 2}])
            with target.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows, [{"value": "1"}, {"value": "2"}])
            self.assertFalse(OUTPUT_STAGING_DIRECTORY.exists())

    def test_row_failure_preserves_previous_target(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            target = Path(directory) / "values.csv"
            target.write_text("accepted\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                write_csv(target, ["value"], _FailingRows())
            self.assertEqual(target.read_text(encoding="utf-8"), "accepted\n")
            self.assertFalse(OUTPUT_STAGING_DIRECTORY.exists())

    def test_json_publication_is_complete_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            target = Path(directory) / "values.json"
            write_json(target, {"z": 2, "a": [1, 3]})
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), {"a": [1, 3], "z": 2})
            self.assertTrue(target.read_text(encoding="utf-8").endswith("\n"))
            self.assertNotIn(b"\r\n", target.read_bytes())
            self.assertFalse(OUTPUT_STAGING_DIRECTORY.exists())

    def test_csv_publication_uses_canonical_lf_newlines(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            target = Path(directory) / "values.csv"
            write_csv(target, ["value"], [{"value": 1}, {"value": 2}])
            self.assertEqual(target.read_bytes(), b"value\n1\n2\n")


if __name__ == "__main__":
    unittest.main()
