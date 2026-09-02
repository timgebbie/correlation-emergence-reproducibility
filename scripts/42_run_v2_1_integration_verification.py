"""Verify the v2.1.0 Figure 12/13 reader-facing integration boundary."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.integrity import sha256
from functions.io_utils import write_csv
from scripts.run_all import ACTIVE_STEPS


CHECK_PATH = PROJECT_ROOT / "diagnostics/v2.1.0-integration-checks.csv"
PANEL_MANIFEST_PATH = PROJECT_ROOT / "outputs/figure-13-panel-manifest-v2.1.csv"

FROZEN_INPUTS = {
    "RELEASE-NOTES-v2.0.0.md": "6e5d20ebd0d30afc8cbf56b63c188f18c9a98b136e27aee17bbee8dd64355ff0",
    "SUPPLEMENTARY-MATERIAL-v2.0.0.tex": "960400980ae7224eca072f71ec9e69ead8bc0c9cc11024a4d48a66d55f403bf4",
    "supplementary-materials/SUPPLEMENTARY-MATERIAL-v2.0.0.pdf": "5152ab809b9826feb24915fcc9c7aa414ab98052b3fedb085315311498bf3b6f",
    "source/source-v1/CATG-RD2Epps-v3-arXiv.tex": "48eea98a6fb084d6ecc397bede4c107a44cae947e16271d66a7041e2997afb5a",
}


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


def main() -> int:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    captions = (PROJECT_ROOT / "captions/caption-register-v2.md").read_text(
        encoding="utf-8"
    )
    public_manifest = (
        PROJECT_ROOT / "provenance/FIGURE-TABLE-MANIFEST-v2.md"
    ).read_text(encoding="utf-8")
    supplement = "\n".join(
        (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        for relative in (
            "SUPPLEMENTARY-MATERIAL-v2.1.0.tex",
            "source/source-v2/NUMERICAL-ALGORITHMS-v2.1.tex",
            "source/source-v2/ORDER-BOOK-SHOCK-RECOVERY-v2.1.tex",
            "source/source-v2/STYLISED-FACTS-RECOVERY-v2.1.tex",
        )
    )
    readme_normalized = re.sub(r"\s+", " ", readme)
    captions_normalized = re.sub(r"\s+", " ", captions)
    supplement_normalized = re.sub(r"\s+", " ", supplement)
    active_paths = [path for _, path in ACTIVE_STEPS]
    panel_rows = _rows(PANEL_MANIFEST_PATH)
    representative_policy = (
        PROJECT_ROOT / "config/config-v2.1.0-representative-paths.json"
    ).read_text(encoding="utf-8")

    figure_numbers = {
        int(match.group(1))
        for match in re.finditer(r"^\| F(\d+) \|", public_manifest, re.MULTILINE)
    }
    missing_pairs = [
        number
        for number in range(1, 14)
        if not any(
            path.with_suffix(".pdf").is_file()
            for path in (PROJECT_ROOT / "figures").glob(f"figure-{number:02d}-*.png")
        )
    ]
    panel_errors: list[str] = []
    for row in panel_rows:
        for path_field, hash_field in (
            ("source_config", "source_config_sha256"),
            ("data_path", "data_sha256"),
            ("pdf_path", "pdf_sha256"),
            ("png_path", "png_sha256"),
        ):
            path = PROJECT_ROOT / row[path_field]
            if not path.is_file() or sha256(path) != row[hash_field]:
                panel_errors.append(row[path_field])

    frozen_errors: dict[str, str] = {}
    for relative, expected in FROZEN_INPUTS.items():
        path = PROJECT_ROOT / relative
        actual = sha256(path) if path.is_file() else "missing"
        if actual != expected:
            frozen_errors[relative] = actual
    qualification = (
        "registered finite periodic-schedule diagnostic",
        "phase-sensitive",
    )
    readme_figure_13_scope = (
        "alpha_u=1",
        "zero cancellation",
        "Poisson refresh clock",
    )
    supplement_figure_13_scope = (
        "\\alpha_u=1",
        "zero cancellation",
        "Poisson refresh clock",
    )
    governance_paths = list(PROJECT_ROOT.rglob("*R7C*"))

    checks = [
        _check("V21I-01", "frozen v2.0.0 and source-v1 inputs", frozen_errors, "no errors", not frozen_errors),
        _check("V21I-02", "README version", "Version: v2.1.0" in readme, "v2.1.0 development identity", "Version: v2.1.0" in readme),
        _check("V21I-03", "public figure sequence", sorted(figure_numbers), "Figures 1 through 13", figure_numbers == set(range(1, 14))),
        _check("V21I-04", "public figure pairs", missing_pairs, "all Figure 1--13 PDF/PNG pairs", not missing_pairs),
        _check("V21I-05", "Figure 11 qualification in README", qualification, "both accepted terms", all(term in readme_normalized for term in qualification)),
        _check("V21I-06", "Figure 11 qualification in caption register", qualification, "both accepted terms", all(term in captions_normalized for term in qualification)),
        _check("V21I-07", "Figure 11 qualification in supplement", qualification, "both accepted terms", all(term in supplement_normalized for term in qualification)),
        _check("V21I-08", "Figure 12 supplement integration", "ORDER-BOOK-SHOCK-RECOVERY-v2.1.tex" in supplement, "accepted source-v2 insert", "ORDER-BOOK-SHOCK-RECOVERY-v2.1.tex" in supplement),
        _check("V21I-09", "Figure 13 supplement integration", "STYLISED-FACTS-RECOVERY-v2.1.tex" in supplement, "accepted source-v2 insert", "STYLISED-FACTS-RECOVERY-v2.1.tex" in supplement),
        _check("V21I-10", "Figure 13 scope in README", readme_figure_13_scope, "all accepted limits", all(term in readme for term in readme_figure_13_scope)),
        _check("V21I-11", "Figure 13 scope in supplement source", supplement_figure_13_scope, "all accepted limits", all(term in supplement for term in supplement_figure_13_scope)),
        _check("V21I-12", "Figure 13 panel manifest", [len(panel_rows), panel_errors], "six rows and no hash errors", len(panel_rows) == 6 and not panel_errors),
        _check("V21I-13", "Figure 13 assembled pair", [(PROJECT_ROOT / "figures/figure-13-stylised-facts-recovery-v2.pdf").is_file(), (PROJECT_ROOT / "figures/figure-13-stylised-facts-recovery-v2.png").is_file()], "both present", all((PROJECT_ROOT / f"figures/figure-13-stylised-facts-recovery-v2{suffix}").is_file() for suffix in (".pdf", ".png"))),
        _check("V21I-14", "active Figure 12 route", "scripts/40_run_order_book_shock_recovery.py" in active_paths, "present", "scripts/40_run_order_book_shock_recovery.py" in active_paths),
        _check("V21I-15", "active Figure 13 route", "scripts/41_run_stylised_facts_recovery.py" in active_paths, "present", "scripts/41_run_stylised_facts_recovery.py" in active_paths),
        _check("V21I-16", "active integration verification", "scripts/42_run_v2_1_integration_verification.py" in active_paths, "present", "scripts/42_run_v2_1_integration_verification.py" in active_paths),
        _check("V21I-17", "R7C governance excluded", governance_paths, "no repository files", not governance_paths),
        _check("V21I-18", "README Figure 12 image", "figures/figure-12-order-book-shock-recovery-v2.png" in readme, "embedded", "![Figure 12:" in readme and "figures/figure-12-order-book-shock-recovery-v2.png" in readme),
        _check("V21I-19", "README Figure 13 image", "figures/figure-13-stylised-facts-recovery-v2.png" in readme, "embedded", "![Figure 13:" in readme and "figures/figure-13-stylised-facts-recovery-v2.png" in readme),
        _check("V21I-20", "audited algorithm source integration", "NUMERICAL-ALGORITHMS-v2.1.tex" in supplement, "included source-v2 insert", "NUMERICAL-ALGORITHMS-v2.1.tex" in supplement),
        _check("V21I-21", "operational coupling algorithm", "-\\kappa_{jk}z_{jk,n}" in supplement, "receiving-front translation field", "-\\kappa_{jk}z_{jk,n}" in supplement and "frozen histories" in supplement),
        _check("V21I-22", "previous-refresh conditional algorithm", "nested map" in supplement, "nested previous-refresh map and conditional moments", "nested map" in supplement and "\\Theta_{q,r}-\\frac{K_{q,r}}{2\\kappa}" in supplement and "e^{-\\kappa(b_j-a_j)}-1" in supplement),
        _check("V21I-23", "autocorrelation estimator equation", "slice-specific Pearson product form" if "\\bar X_{L,k}" in supplement and "\\bar X_{R,k}" in supplement and "\\left[\\sum" in supplement and "\\right] \\left[\\sum" in supplement_normalized else "missing or malformed", "separate lagged-slice means and product of variance factors", "\\bar X_{L,k}" in supplement and "\\bar X_{R,k}" in supplement and "\\left[\\sum" in supplement and "\\right] \\left[\\sum" in supplement_normalized and "\\widehat\\rho_X(0)=1" in supplement),
        _check("V21I-24", "stable representative paths", "Figure 11 path 4; Figure 13 path 2", "predeclared paths with ULP validation", '"predeclared_path_index": 4' in representative_policy and '"predeclared_master_path_index": 2' in representative_policy and '"distance_tolerance_ulps": 64' in representative_policy),
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
        print(f"v2.1.0 integration verification failed: {len(failures)} check(s).")
        return 1
    print(f"v2.1.0 integration verification completed: {len(checks)} checks verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
