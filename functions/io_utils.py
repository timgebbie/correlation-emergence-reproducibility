"""Small path, configuration, and tabular-output helpers."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Iterable, Mapping
import uuid

from functions.figure_io import sync_completed_file


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_STAGING_DIRECTORY = PROJECT_ROOT / ".output-staging"


def remove_orphaned_output_staging_files() -> None:
    """Remove incomplete tabular publications left by an interrupted route."""

    if OUTPUT_STAGING_DIRECTORY.is_dir():
        for temporary in OUTPUT_STAGING_DIRECTORY.iterdir():
            if temporary.is_file():
                temporary.unlink(missing_ok=True)
        try:
            OUTPUT_STAGING_DIRECTORY.rmdir()
        except OSError:
            pass


def _staging_path(target: Path) -> Path:
    OUTPUT_STAGING_DIRECTORY.mkdir(parents=True, exist_ok=True)
    return OUTPUT_STAGING_DIRECTORY / (
        f"{target.parent.name}-{target.stem}-{uuid.uuid4().hex}.tmp{target.suffix}"
    )


def _finish_publication(temporary: Path, target: Path) -> None:
    """Commit one complete same-filesystem staged output."""

    sync_completed_file(temporary)
    os.replace(temporary, target)


def load_config() -> dict:
    with (PROJECT_ROOT / "config" / "config-v1.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def ensure_output_directories() -> None:
    for name in ("outputs", "figures", "tables", "captions", "diagnostics", "supplementary-materials"):
        (PROJECT_ROOT / name).mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _staging_path(path)
    try:
        with temporary.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
        _finish_publication(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
        try:
            OUTPUT_STAGING_DIRECTORY.rmdir()
        except OSError:
            pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = _staging_path(path)
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
        _finish_publication(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
        try:
            OUTPUT_STAGING_DIRECTORY.rmdir()
        except OSError:
            pass


def latex_escape(value: object) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(char, char) for char in text)


__all__ = [
    "PROJECT_ROOT",
    "OUTPUT_STAGING_DIRECTORY",
    "load_config",
    "ensure_output_directories",
    "remove_orphaned_output_staging_files",
    "write_csv",
    "read_csv",
    "write_json",
    "latex_escape",
]
