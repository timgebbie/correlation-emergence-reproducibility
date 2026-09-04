"""Audit the v2.1.0 release surface and scientific publication boundary."""

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
CHECK_PATH = PROJECT_ROOT / "diagnostics/v2.1.0-release-checks.csv"


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
    clock_impact_rows = _rows(
        PROJECT_ROOT / "diagnostics/clock-impact-science-math-checks-v2.1.csv"
    )
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
    figure_7_stems = (
        "figure-07a-clock-only-epps-v2",
        "figure-07b-coupling-only-epps-v2",
        "figure-07c-combined-epps-v2",
    )
    missing_figure_7_pairs = [
        stem
        for stem in figure_7_stems
        if not all(
            (PROJECT_ROOT / "figures" / f"{stem}.{suffix}").is_file()
            for suffix in ("pdf", "png")
        )
    ]
    figure_sizes = {
        "7a": _png_size(PROJECT_ROOT / "figures/figure-07a-clock-only-epps-v2.png"),
        "7b": _png_size(PROJECT_ROOT / "figures/figure-07b-coupling-only-epps-v2.png"),
        "7c": _png_size(PROJECT_ROOT / "figures/figure-07c-combined-epps-v2.png"),
        "12": _png_size(PROJECT_ROOT / "figures/figure-12-order-book-shock-recovery-v2.png"),
        "13": _png_size(PROJECT_ROOT / "figures/figure-13-stylised-facts-recovery-v2.png"),
        "14": _png_size(PROJECT_ROOT / "figures/figure-14-clock-subordinated-impact-v2.png"),
    }
    required_manifest_paths = {
        "CITATION.cff",
        "RELEASE-NOTES-v2.1.0.md",
        "config/config-v2.1.0-release.json",
        "scripts/44_run_v2_1_release_audit.py",
        "tests/test_v2_1_release.py",
    }
    active_todo_commands = [
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in PROJECT_ROOT.rglob("*.tex")
        if re.search(r"\\todo(?:\[|\{)", path.read_text(encoding="utf-8"))
    ]
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
    internal_stage_pattern = re.compile(r"\bR[0-9]+[A-Z]?\b", re.IGNORECASE)
    internal_stage_text_hits = []
    text_suffixes = {".cff", ".csv", ".json", ".md", ".py", ".tex", ".txt"}
    for relative in sorted(archive_paths):
        path = PROJECT_ROOT / relative
        if path.suffix.lower() not in text_suffixes:
            continue
        content = path.read_text(encoding="utf-8")
        if internal_stage_pattern.search(content):
            internal_stage_text_hits.append(relative)
    internal_stage_path_hits = [
        relative
        for relative in sorted(archive_paths)
        if re.search(r"(^|[/_.-])r[0-9]+[a-z]?([/_.-]|$)", relative, re.IGNORECASE)
    ]

    checks = [
        _check("V21R-01", "release configuration identity", [configuration["schema_version"], configuration["scope"]], "v2.1.0 release conformity", configuration["schema_version"] == "2.1.0" and configuration["scope"] == "release_conformity_and_science_consistency"),
        _check("V21R-02", "frozen v2.0.0 and source-v1 inputs", frozen_errors, "no hash errors", not frozen_errors),
        _check("V21R-03", "accepted Figures 12--14 and supplement", evidence_errors, "no hash errors", not evidence_errors),
        _check("V21R-04", "README release identity", "Version: v2.1.0" in readme and "development candidate" not in readme, "v2.1.0 release identity", "Version: v2.1.0" in readme and "development candidate" not in readme),
        _check("V21R-05", "changelog release identity", "`v2.1.0` — 2026-09-04" in changelog, "dated v2.1.0 entry", "`v2.1.0` — 2026-09-04" in changelog),
        _check("V21R-06", "citation version", ["version: \"2.1.0\"" in citation, "date-released:" in citation], "v2.1.0 and no premature release date", "version: \"2.1.0\"" in citation and "date-released:" not in citation),
        _check("V21R-07", "v2.1.0 release notes", [token for token in ("Figure 7", "Figure 12", "Figure 13", "Figure 14") if token in release_notes], "all release topics", all(token in release_notes for token in ("Figure 7", "Figure 12", "Figure 13", "Figure 14"))),
        _check("V21R-08", "streamlined publication contract", sorted(publication), "five fixed release fields", set(publication) == {"version", "tag", "release_title", "archive_name", "single_release_archive"}),
        _check("V21R-09", "final release identity", [publication["version"], publication["tag"], publication["archive_name"]], "fixed v2.1.0 identity", publication["version"] == "v2.1.0" and publication["tag"] == "v2.1.0" and publication["archive_name"] == "correlation-emergence-reproducibility-v2.1.0.zip"),
        _check("V21R-10", "public figure sequence", sorted(figure_numbers), "Figures 1 through 14", figure_numbers == set(range(1, 15))),
        _check("V21R-11", "public figure PDF/PNG pairs", {"numbered": missing_pairs, "figure_7_standalones": missing_figure_7_pairs}, "all Figure 1--14 pairs including Figure 7a--7c", not missing_pairs and not missing_figure_7_pairs),
        _check("V21R-12", "reader-facing image resolution", figure_sizes, "F7a--F7c 1408x1408; F12 4500x3600; F13 3960x4560; F14 3600x2580", figure_sizes == {"7a": (1408, 1408), "7b": (1408, 1408), "7c": (1408, 1408), "12": (4500, 3600), "13": (3960, 4560), "14": (3600, 2580)}),
        _check("V21R-13", "enriched supplement exists", (PROJECT_ROOT / "supplementary-materials/SUPPLEMENTARY-MATERIAL-v2.1.0.pdf").stat().st_size, "nonempty compiled PDF", (PROJECT_ROOT / "supplementary-materials/SUPPLEMENTARY-MATERIAL-v2.1.0.pdf").stat().st_size > 100_000),
        _check("V21R-14", "algorithmic supplement and todonote surface", {"algorithm_controls": [token for token in ("algorithmicx", "renewal-clock-construction", "paired-clock-impact") if token in supplement], "active_todo_commands": active_todo_commands}, "all three algorithm controls and no active todo commands", all(token in supplement for token in ("algorithmicx", "renewal-clock-construction", "paired-clock-impact")) and not active_todo_commands),
        _check("V21R-15", "README embeds Figures 12--14", [f"![Figure {number}:" in readme for number in (12, 13, 14)], "all embedded", all(f"![Figure {number}:" in readme for number in (12, 13, 14))),
        _check("V21R-16", "exogenous-memory boundary", scientific, "no endogenous or empirical claim and no refit", scientific["long_memory_input"] == "declared_exogenous_heavy_tailed_order_splitting" and scientific["endogenous_memory_claim"] is False and scientific["empirical_calibration_claim"] is False and scientific["parameters_refitted"] is False),
        _check("V21R-17", "clock-impact science and mathematics checks", [len(clock_impact_rows), Counter(row["status"] for row in clock_impact_rows)], "20 verified, zero failures", len(clock_impact_rows) == 20 and all(row["status"] == "Verified" for row in clock_impact_rows)),
        _check("V21R-18", "v2.1.0 integration checks", [len(integration_rows), Counter(row["status"] for row in integration_rows)], "32 verified, zero failures", len(integration_rows) == 32 and all(row["status"] == "Verified" for row in integration_rows)),
        _check("V21R-19", "all retained diagnostics", dict(statuses), "zero failed statuses", statuses.get("Failed", 0) == 0),
        _check("V21R-20", "accepted Stage 7 qualifications", qualification_rows, "closure records exactly six", len(qualification_rows) == 1 and qualification_rows[0]["observed"] == "6" and qualification_rows[0]["status"] == "Verified" and scientific["accepted_stage_7_qualifications"] == 6),
        _check("V21R-21", "final active release audit", active_paths[-1], "scripts/44_run_v2_1_release_audit.py", active_paths[-1] == "scripts/44_run_v2_1_release_audit.py"),
        _check("V21R-22", "single reproduction entry point", configuration["active_route"]["entrypoints"], "scripts/run_all.py only", configuration["active_route"]["entrypoints"] == ["scripts/run_all.py"]),
        _check("V21R-23", "release files in complete manifest", sorted(required_manifest_paths - archive_paths), "no missing paths", required_manifest_paths <= archive_paths),
        _check("V21R-24", "README local links", local_link_errors, "no missing local target", not local_link_errors),
        _check("V21R-25", "license surface", [(PROJECT_ROOT / "LICENSE").is_file(), (PROJECT_ROOT / "CONTENT-LICENSE.md").is_file(), "license: MIT" in citation], "code and content licenses declared", (PROJECT_ROOT / "LICENSE").is_file() and (PROJECT_ROOT / "CONTENT-LICENSE.md").is_file() and "license: MIT" in citation),
        _check("V21R-26", "private governance files excluded", governance_paths, "none", not governance_paths),
        _check("V21R-27", "cache and staging paths excluded", cache_paths, "none", not cache_paths),
        _check("V21R-28", "single release archive policy", publication["single_release_archive"], "true", publication["single_release_archive"] is True),
        _check("V21R-29", "internal recovery labels absent from tracked text", internal_stage_text_hits, "none", not internal_stage_text_hits),
        _check("V21R-30", "internal recovery labels absent from tracked paths", internal_stage_path_hits, "none", not internal_stage_path_hits),
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
        print(f"v2.1.0 release audit failed: {len(failures)} check(s).")
        return 1
    print(f"v2.1.0 release audit completed: {len(checks)} checks verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
