"""Run the complete active v1.0.0 reproducibility route."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _run(label: str, command: list[str], environment: dict[str, str]) -> None:
    print(f"\n[{label}] {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=PROJECT_ROOT, env=environment, check=True)


def main() -> int:
    environment = os.environ.copy()
    environment.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib-cache"))
    python = sys.executable
    steps = (
        ("diagnostics", [python, "scripts/01_run_diagnostics.py"]),
        ("tables", [python, "scripts/02_make_tables.py"]),
        ("figures and curve data", [python, "scripts/03_generate_figures.py"]),
        ("sensitivity and robustness", [python, "scripts/04_run_sensitivity_checks.py"]),
        ("regression tests", [python, "-m", "unittest", "discover", "-s", "tests", "-v"]),
    )
    try:
        for label, command in steps:
            _run(label, command, environment)
    except subprocess.CalledProcessError as error:
        print(f"\nActive route stopped after an unsuccessful command (exit code {error.returncode}).")
        return error.returncode or 1
    print("\nActive v1.0.0 reproducibility route completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
