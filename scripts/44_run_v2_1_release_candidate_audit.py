"""Audit the untagged v2.1.0 release-candidate and publication boundary."""

from __future__ import annotations

import csv
import json
import re
import struct
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.integrity import (
    ARCHIVE_MANIFEST_PATH,
    accepted_input_errors,
    read_manifest,
)
from functions.io_utils import write_csv
from scripts.run_all import ACTIVE_STEPS


CONFIG_PATH = PROJECT_ROOT / "config/config-v2.1.0-release.json"
CHECK_PATH = PROJECT_ROOT / "diagnostics/v2.1.0-release-candidate-checks.csv"


def _check(
    identifier: str,
    claim: str,
    observed: object,
    criterion: str,
    passed: bool,
) -> dict[str, object]:
    return {
        "check_id": identifier,
        "claim": claim,
        "observed": observed,
        "criterion": criterion,
        "status": "Verified" if passed else "Failed",
        "software_version": "2.1.0",
    }


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", header[16:24])


def _missing_local_links(markdown: str) -> list[str]:
    missing: set[str] = set()
    for match in re.finditer(r"!?\[[^\]]*\]\(([^)]+)\)", markdown):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        path = target.split("#", 1)[0]
        if path and not (PROJECT_ROOT / path).exists():
            missing.add(target)
    return sorted(missing)


def _diagnostic_statuses() -> Counter[str]:
    statuses: Counter[str] = Counter()
    for path in sorted((PROJECT_ROOT / "diagnostics").glob("*.csv")):
        if path == CHECK_PATH:
            continue
        for row in _rows(path):
            status = row.get("status", "").strip()
            if status:
                statuses[status] += 1
    return statuses


def main() -> int:
    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    accepted_parent = configuration["accepted_parent"]
    scientific = configuration["scientific_contract"]
    publication = configuration["publication_contract"]
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    changelog = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    citation = (PROJECT_ROOT / "CITATION.cff").read_text(encoding="utf-8")
    release_notes = (PROJECT_ROOT / "RELEASE-NOTES-v2.1.0.md").read_text(
        encoding="utf-8"
    )
    supplement = "\n".join(
        (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "SUPPLEMENTARY-MATERIAL-v2.1.0.tex",
            "source/source-v2/NUMERICAL-ALGORITHMS-v2.1.tex",
            "source/source-v2/LONG-MEMORY-CLOCK-IMPACT-v2.1.tex",
        )
    )
    public_manifest = (
        PROJECT_ROOT / "provenance/FIGURE-TABLE-MANIFEST-v2.md"
    ).read_text(encoding="utf-8")
    archive_paths = set(read_manifest(ARCHIVE_MANIFEST_PATH))
    active_paths = [path for _, path in ACTIVE_STEPS]

    frozen_errors = accepted_input_errors(configuration["frozen_inputs"])
    evidence_errors = accepted_input_errors(configuration["accepted_evidence"])
    r13_rows = _rows(PROJECT_ROOT / "diagnostics/r13-science-math-checks-v2.1.csv")
    integration_rows = _rows(
        PROJECT_ROOT / "diagnostics/v2.1.0-integration-checks.csv"
    )
    closure_rows = _rows(PROJECT_ROOT / "diagnostics/stage-7-closure-checks-v1.7.csv")
    qualification_rows = [row for row in closure_rows if row["check_id"] == "S7CL-15"]
    statuses = _diagnostic_statuses()

    figure_numbers = {
        int(match.group(1))
        for match in re.finditer(r"^\| F(\d+) \|", public_manifest, re.MULTILINE)
    }
    missing_pairs = []
    for number in scientific["public_figure_numbers"]:
        pngs = list((PROJECT_ROOT / "figures").glob(f"figure-{number:02d}-*.png"))
        if not pngs or not any(path.with_suffix(".pdf").is_file() for path in pngs):
            missing_pairs.append(number)
    figure_sizes = {
        "12": _png_size(PROJECT_ROOT / "figures/figure-12-order-book-shock-recovery-v2.png"),
        "13": _png_size(PROJECT_ROOT / "figures/figure-13-stylised-facts-recovery-v2.png"),
        "14": _png_size(PROJECT_ROOT / "figures/figure-14-clock-subordinated-impact-v2.png"),
    }
    required_manifest_paths = {
        "CITATION.cff",
        "RELEASE-NOTES-v2.1.0.md",
        "config/config-v2.1.0-release.json",
        "scripts/44_run_v2_1_release_candidate_audit.py",
        "tests/test_v2_1_release_candidate.py",
    }
    governance_paths = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in PROJECT_ROOT.rglob("*")
        if path.is_file()
        and any(
            token in path.name.lower()
            for token in ("acceptance-attestation", "gate-record", "disaster-recovery")
        )
    ]
    cache_paths = sorted(
        path
        for path in archive_paths
        if "__pycache__" in path
        or path.endswith(".pyc")
        or ".figure-staging" in path
        or ".output-staging" in path
    )
    local_link_errors = _missing_local_links(readme)

    checks = [
        _check("R14-01", "accepted R13 parent commit", accepted_parent["commit"], "d329b00d066c181ae416799688f41401e70c1a80", accepted_parent["commit"] == "d329b00d066c181ae416799688f41401e70c1a80"),
        _check("R14-02", "accepted R13 tree", accepted_parent["tree"], "57a28c0789c5dda9a813228fe36db2c080fa9f05", accepted_parent["tree"] == "57a28c0789c5dda9a813228fe36db2c080fa9f05"),
        _check("R14-03", "accepted R13 recovery bundle", accepted_parent["stage_bundle_sha256"], "57ea08936bbf3cd0aac2d497eab845e78b4789f6441620a0b03e57fd6a5aca16", accepted_parent["stage_bundle_sha256"] == "57ea08936bbf3cd0aac2d497eab845e78b4789f6441620a0b03e57fd6a5aca16"),
        _check("R14-04", "frozen v2.0.0 and source-v1 inputs", frozen_errors, "no hash errors", not frozen_errors),
        _check("R14-05", "accepted Figures 12--14 and supplement", evidence_errors, "no hash errors", not evidence_errors),
        _check("R14-06", "README candidate identity", "Version: v2.1.0 development candidate" in readme, "explicit v2.1.0 development candidate", "Version: v2.1.0 development candidate" in readme),
        _check("R14-07", "changelog candidate identity", "`v2.1.0` — 2026-09-04 — untagged release candidate" in changelog, "dated untagged release candidate", "`v2.1.0` — 2026-09-04 — untagged release candidate" in changelog),
        _check("R14-08", "citation candidate version", ["version: \"2.1.0\"" in citation, "date-released:" in citation], "v2.1.0 and no release date", "version: \"2.1.0\"" in citation and "date-released:" not in citation),
        _check("R14-09", "v2.1.0 release notes", [token for token in ("Figure 12", "Figure 13", "Figure 14", "not been tagged") if token in release_notes], "all candidate topics and deferred status", all(token in release_notes for token in ("Figure 12", "Figure 13", "Figure 14", "not been tagged"))),
        _check("R14-10", "publication remains untagged", publication, "push untagged candidate; inspect before tag; no tag or GitHub Release", publication["repository_state"] == "untagged_v2.1.0_candidate" and publication["push_untagged_state_first"] is True and publication["inspect_and_correct_before_tag"] is True and publication["tag_created"] is False and publication["github_release_created"] is False),
        _check("R14-11", "final candidate identity", [publication["version"], publication["tag"], publication["archive_name"]], "fixed v2.1.0 identity", publication["version"] == "v2.1.0" and publication["tag"] == "v2.1.0" and publication["archive_name"] == "correlation-emergence-reproducibility-v2.1.0.zip"),
        _check("R14-12", "public figure sequence", sorted(figure_numbers), "Figures 1 through 14", figure_numbers == set(range(1, 15))),
        _check("R14-13", "public figure PDF/PNG pairs", missing_pairs, "all Figure 1--14 pairs", not missing_pairs),
        _check("R14-14", "reader-facing image resolution", figure_sizes, "F12 4500x3600, F13 3960x4560, F14 3600x2580", figure_sizes == {"12": (4500, 3600), "13": (3960, 4560), "14": (3600, 2580)}),
        _check("R14-15", "enriched supplement exists", (PROJECT_ROOT / "supplementary-materials/SUPPLEMENTARY-MATERIAL-v2.1.0.pdf").stat().st_size, "nonempty compiled PDF", (PROJECT_ROOT / "supplementary-materials/SUPPLEMENTARY-MATERIAL-v2.1.0.pdf").stat().st_size > 100_000),
        _check("R14-16", "algorithmic supplement surface", [token for token in ("algorithmicx", "renewal-clock-construction", "paired-clock-impact") if token in supplement], "all three algorithm controls", all(token in supplement for token in ("algorithmicx", "renewal-clock-construction", "paired-clock-impact"))),
        _check("R14-17", "README embeds Figures 12--14", [f"![Figure {number}:" in readme for number in (12, 13, 14)], "all embedded", all(f"![Figure {number}:" in readme for number in (12, 13, 14))),
        _check("R14-18", "exogenous-memory boundary", scientific, "no endogenous or empirical claim and no refit", scientific["long_memory_input"] == "declared_exogenous_heavy_tailed_order_splitting" and scientific["endogenous_memory_claim"] is False and scientific["empirical_calibration_claim"] is False and scientific["parameters_refitted"] is False),
        _check("R14-19", "R13 science and mathematics checks", [len(r13_rows), Counter(row["status"] for row in r13_rows)], "20 verified, zero failures", len(r13_rows) == 20 and all(row["status"] == "Verified" for row in r13_rows)),
        _check("R14-20", "v2.1.0 integration checks", [len(integration_rows), Counter(row["status"] for row in integration_rows)], "32 verified, zero failures", len(integration_rows) == 32 and all(row["status"] == "Verified" for row in integration_rows)),
        _check("R14-21", "all retained diagnostics", dict(statuses), "zero failed statuses", statuses.get("Failed", 0) == 0),
        _check("R14-22", "accepted Stage 7 qualifications", qualification_rows, "closure records exactly six", len(qualification_rows) == 1 and qualification_rows[0]["observed"] == "6" and qualification_rows[0]["status"] == "Verified" and scientific["accepted_stage_7_qualifications"] == 6),
        _check("R14-23", "R14 is final active audit", active_paths[-1], "scripts/44_run_v2_1_release_candidate_audit.py", active_paths[-1] == "scripts/44_run_v2_1_release_candidate_audit.py"),
        _check("R14-24", "single reproduction entry point", configuration["active_route"]["entrypoints"], "scripts/run_all.py only", configuration["active_route"]["entrypoints"] == ["scripts/run_all.py"]),
        _check("R14-25", "R14 files in complete manifest", sorted(required_manifest_paths - archive_paths), "no missing paths", required_manifest_paths <= archive_paths),
        _check("R14-26", "README local links", local_link_errors, "no missing local target", not local_link_errors),
        _check("R14-27", "license surface", [(PROJECT_ROOT / "LICENSE").is_file(), (PROJECT_ROOT / "CONTENT-LICENSE.md").is_file(), "license: MIT" in citation], "code and content licenses declared", (PROJECT_ROOT / "LICENSE").is_file() and (PROJECT_ROOT / "CONTENT-LICENSE.md").is_file() and "license: MIT" in citation),
        _check("R14-28", "governance files excluded from scientific repository", governance_paths, "none", not governance_paths),
        _check("R14-29", "cache and staging paths excluded", cache_paths, "none", not cache_paths),
        _check("R14-30", "single release archive policy", publication["separate_verification_only_archive"], "false", publication["separate_verification_only_archive"] is False),
    ]

    write_csv(
        CHECK_PATH,
        ["check_id", "claim", "observed", "criterion", "status", "software_version"],
        checks,
    )
    failures = [row for row in checks if row["status"] != "Verified"]
    for row in checks:
        print(f"{row['check_id']}: {row['status']} - {row['claim']}")
    if failures:
        print(f"R14 release-candidate audit failed: {len(failures)} check(s).")
        return 1
    print(f"R14 release-candidate audit completed: {len(checks)} checks verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
