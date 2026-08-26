"""Verify that active execution did not mutate immutable project material."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.integrity import IMMUTABLE_MANIFEST_PATH, verify_manifest


def main() -> int:
    count = verify_manifest(IMMUTABLE_MANIFEST_PATH)
    print(f"Immutable-source manifest verified: {count} entries, 0 failures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
