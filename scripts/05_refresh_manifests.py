"""Refresh the immutable-source and complete-archive SHA-256 manifests."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.integrity import ARCHIVE_MANIFEST_PATH, IMMUTABLE_MANIFEST_PATH, sha256


IGNORED_PARTS = {
    ".controlled-py312",
    ".git",
    ".figure-staging",
    ".matplotlib-cache",
    ".output-staging",
    ".render-staging",
    ".venv",
    "__pycache__",
    "tmp",
}
GENERATED_TOP_LEVEL = {"diagnostics", "figures", "outputs", "tables"}
GENERATED_ROOT_FILES: set[str] = set()


def _controlled_files() -> list[Path]:
    result = []
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(PROJECT_ROOT)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path == ARCHIVE_MANIFEST_PATH:
            continue
        result.append(path)
    return sorted(result, key=lambda path: path.relative_to(PROJECT_ROOT).as_posix())


def _immutable_files(files: list[Path]) -> list[Path]:
    return [
        path
        for path in files
        if path != IMMUTABLE_MANIFEST_PATH
        and path.relative_to(PROJECT_ROOT).parts[0] not in GENERATED_TOP_LEVEL
        and path.relative_to(PROJECT_ROOT).as_posix() not in GENERATED_ROOT_FILES
    ]


def _write_manifest(path: Path, files: list[Path]) -> None:
    lines = [
        f"{sha256(source)}  {source.relative_to(PROJECT_ROOT).as_posix()}"
        for source in files
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    files = _controlled_files()
    immutable = _immutable_files(files)
    _write_manifest(IMMUTABLE_MANIFEST_PATH, immutable)
    files = _controlled_files()
    _write_manifest(ARCHIVE_MANIFEST_PATH, files)
    print(f"Immutable-source manifest refreshed: {len(immutable)} entries.")
    print(f"Complete-archive manifest refreshed: {len(files)} entries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
