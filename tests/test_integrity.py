"""Tests for archive preflight, accepted-input, and runtime contracts."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from functions.integrity import (
    PREFLIGHT_ENVIRONMENT_VARIABLE,
    accepted_input_errors,
    archive_preflight_token,
    manifest_errors,
    read_manifest,
    sha256,
    verify_manifest,
)
from functions.runtime_contract import (
    EXPECTED_PACKAGE_VERSIONS,
    SUPPORTED_PYTHON_MINORS,
    runtime_version_errors,
)


ROOT = Path(__file__).resolve().parents[1]


class IntegrityContractTests(unittest.TestCase):
    def test_manifest_verification_detects_change_and_missing_file(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            first = root / "first.txt"
            second = root / "second.txt"
            first.write_bytes(b"accepted\n")
            second.write_bytes(b"present\n")
            manifest = root / "manifest.txt"
            manifest.write_text(
                f"{sha256(first)}  first.txt\n{sha256(second)}  second.txt\n",
                encoding="utf-8",
                newline="\n",
            )
            self.assertEqual(verify_manifest(manifest, project_root=root), 2)
            first.write_bytes(b"changed\n")
            second.unlink()
            self.assertEqual(set(manifest_errors(manifest, project_root=root)), {"first.txt", "second.txt"})

    def test_preflight_uses_verified_archive_state_for_accepted_generated_input(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            generated = root / "outputs" / "accepted.csv"
            generated.parent.mkdir()
            generated.write_bytes(b"accepted\n")
            accepted_digest = sha256(generated)
            manifest = root / "manifest.txt"
            manifest.write_text(
                f"{accepted_digest}  outputs/accepted.csv\n",
                encoding="utf-8",
                newline="\n",
            )
            records = [{"path": "outputs/accepted.csv", "sha256": accepted_digest}]
            generated.write_bytes(b"platform-regenerated\r\n")
            self.assertTrue(
                accepted_input_errors(records, project_root=root, archive_manifest_path=manifest)
            )
            with patch.dict(
                os.environ,
                {PREFLIGHT_ENVIRONMENT_VARIABLE: archive_preflight_token(manifest)},
            ):
                self.assertFalse(
                    accepted_input_errors(records, project_root=root, archive_manifest_path=manifest)
                )

    def test_active_manifest_syntax_and_runtime_are_frozen(self) -> None:
        archive = ROOT / "FILE-MANIFEST-SHA256.txt"
        immutable = ROOT / "IMMUTABLE-MANIFEST-SHA256.txt"
        self.assertTrue(read_manifest(archive))
        self.assertTrue(read_manifest(immutable))
        self.assertIn(sys.version_info[:2], SUPPORTED_PYTHON_MINORS)
        self.assertFalse(runtime_version_errors())
        requirements = {
            line.strip() for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        self.assertEqual(
            requirements,
            {f"{package}=={version}" for package, version in EXPECTED_PACKAGE_VERSIONS.items()},
        )


if __name__ == "__main__":
    unittest.main()
