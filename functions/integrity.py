"""Archive, accepted-input, and immutable-source integrity helpers."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_MANIFEST_PATH = PROJECT_ROOT / "FILE-MANIFEST-SHA256.txt"
IMMUTABLE_MANIFEST_PATH = PROJECT_ROOT / "IMMUTABLE-MANIFEST-SHA256.txt"
PREFLIGHT_ENVIRONMENT_VARIABLE = "CORRELATION_EMERGENCE_ARCHIVE_PREFLIGHT"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line:
            continue
        try:
            digest, relative = raw_line.split("  ", 1)
        except ValueError as error:
            raise ValueError(f"invalid manifest line {line_number}: {raw_line!r}") from error
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"invalid SHA-256 on manifest line {line_number}")
        if not relative or relative in entries:
            raise ValueError(f"invalid or duplicate manifest path on line {line_number}")
        entries[relative] = digest
    return entries


def manifest_errors(path: Path, *, project_root: Path = PROJECT_ROOT) -> dict[str, tuple[str, str]]:
    errors: dict[str, tuple[str, str]] = {}
    for relative, expected in read_manifest(path).items():
        target = project_root / relative
        actual = sha256(target) if target.is_file() else "missing"
        if actual != expected:
            errors[relative] = (actual, expected)
    return errors


def verify_manifest(path: Path, *, project_root: Path = PROJECT_ROOT) -> int:
    entries = read_manifest(path)
    errors = manifest_errors(path, project_root=project_root)
    if errors:
        preview = dict(list(errors.items())[:10])
        suffix = "" if len(errors) <= 10 else f" (plus {len(errors) - 10} more)"
        raise RuntimeError(f"manifest verification failed: {preview}{suffix}")
    return len(entries)


def archive_preflight_token(path: Path = ARCHIVE_MANIFEST_PATH) -> str:
    return sha256(path)


def archive_preflight_active(path: Path = ARCHIVE_MANIFEST_PATH) -> bool:
    return os.environ.get(PREFLIGHT_ENVIRONMENT_VARIABLE) == archive_preflight_token(path)


def accepted_input_errors(
    records: Iterable[Mapping[str, object]],
    *,
    project_root: Path = PROJECT_ROOT,
    archive_manifest_path: Path = ARCHIVE_MANIFEST_PATH,
) -> dict[str, tuple[str, str]]:
    """Validate accepted inputs against fresh-archive state or current bytes.

    During ``run_all.py``, the complete archive is verified before any generator
    runs. Later stages therefore compare registered accepted hashes with that
    verified preflight manifest, allowing an earlier stage to regenerate the
    same scientific output with platform-specific bytes. A standalone stage has
    no preflight token and retains strict current-byte checking.
    """

    use_preflight = archive_preflight_active(archive_manifest_path)
    archive_entries = read_manifest(archive_manifest_path) if use_preflight else {}
    errors: dict[str, tuple[str, str]] = {}
    for record in records:
        relative = str(record["path"])
        expected = str(record["sha256"])
        target = project_root / relative
        if use_preflight:
            actual = archive_entries.get(relative, "missing-from-archive-manifest")
            if not target.is_file():
                actual = "missing"
        else:
            actual = sha256(target) if target.is_file() else "missing"
        if actual != expected:
            errors[relative] = (actual, expected)
    return errors


def snapshot_hashes(
    records: Iterable[Mapping[str, object]], *, project_root: Path = PROJECT_ROOT
) -> dict[str, str]:
    return {
        str(record["path"]): sha256(project_root / str(record["path"]))
        for record in records
    }


def snapshot_errors(
    snapshot: Mapping[str, str], *, project_root: Path = PROJECT_ROOT
) -> dict[str, tuple[str, str]]:
    errors: dict[str, tuple[str, str]] = {}
    for relative, expected in snapshot.items():
        target = project_root / relative
        actual = sha256(target) if target.is_file() else "missing"
        if actual != expected:
            errors[relative] = (actual, expected)
    return errors


__all__ = [
    "ARCHIVE_MANIFEST_PATH",
    "IMMUTABLE_MANIFEST_PATH",
    "PREFLIGHT_ENVIRONMENT_VARIABLE",
    "accepted_input_errors",
    "archive_preflight_active",
    "archive_preflight_token",
    "manifest_errors",
    "read_manifest",
    "sha256",
    "snapshot_errors",
    "snapshot_hashes",
    "verify_manifest",
]
