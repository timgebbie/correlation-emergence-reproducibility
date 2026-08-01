"""Small path, configuration, and tabular-output helpers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_config() -> dict:
    with (PROJECT_ROOT / "config" / "config-v1.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def ensure_output_directories() -> None:
    for name in ("outputs", "figures", "tables", "captions", "diagnostics", "supplementary-materials"):
        (PROJECT_ROOT / name).mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


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
    "load_config",
    "ensure_output_directories",
    "write_csv",
    "read_csv",
    "write_json",
    "latex_escape",
]
