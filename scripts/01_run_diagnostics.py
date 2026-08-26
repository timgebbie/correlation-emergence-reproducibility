"""Run claim-relevant numerical diagnostics and record machine-readable results."""

from __future__ import annotations

import sys
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.diagnostic_checks import run_diagnostic_checks
from functions.io_utils import ensure_output_directories, load_config, write_csv, write_json


REPORT_PATH = PROJECT_ROOT / "TEST-REPORT-v1.0.0.md"


def _stable_report_date() -> str:
    """Preserve the accepted report date across ordinary reruns."""

    if REPORT_PATH.is_file():
        match = re.search(
            r"^Date: (\d{4}-\d{2}-\d{2})$",
            REPORT_PATH.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        )
        if match:
            return match.group(1)
    return "2026-08-01"


def main() -> int:
    ensure_output_directories()
    config = load_config()
    results = run_diagnostic_checks(config)
    rows = [result.row() for result in results]
    fieldnames = list(rows[0].keys())
    write_csv(PROJECT_ROOT / "diagnostics" / "diagnostic-results-v1.csv", fieldnames, rows)
    write_json(PROJECT_ROOT / "diagnostics" / "diagnostic-results-v1.json", rows)

    failures = [result for result in results if result.status != "Verified"]
    report_lines = [
        "# Test report - v1.0.0",
        "",
        "Artefact status: **diagnostic output**",
        "",
        f"Date: {_stable_report_date()}",
        "",
        f"Result: **{len(results) - len(failures)} verified; {len(failures)} failed**",
        "",
        "| ID | Diagnostic | Status | Maximum error |",
        "|---|---|---:|---:|",
    ]
    report_lines.extend(
        f"| {result.diagnostic_id} | {result.diagnostic} | {result.status} | {result.maximum_error:.3e} |"
        for result in results
    )
    report_lines.extend(
        [
            "",
            "These checks support numerical reliability for the stated deterministic route. They do not prove the paper's modelling approximations or validate the model empirically.",
            "",
        ]
    )
    REPORT_PATH.write_text(
        "\n".join(report_lines), encoding="utf-8", newline="\n"
    )

    for result in results:
        print(f"{result.diagnostic_id}: {result.status} - {result.diagnostic}")
    if failures:
        print(f"Diagnostic route failed: {len(failures)} check(s) require attention.")
        return 1
    print(f"Diagnostic route completed: {len(results)} checks verified, 0 failures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
