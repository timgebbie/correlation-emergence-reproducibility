"""Verify the frozen v2.0.0 claims retained in the current repository."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from functions.integrity import ARCHIVE_MANIFEST_PATH, accepted_input_errors, read_manifest
from functions.io_utils import write_csv
from scripts.run_all import ACTIVE_STEPS


CONFIG_PATH = PROJECT_ROOT / "config" / "config-v2.0.0.json"
CHECK_PATH = PROJECT_ROOT / "diagnostics" / "release-verification-checks-v2.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "final-estimator-aware-epps-summary-v1.9.csv"
CURVE_PATH = PROJECT_ROOT / "outputs" / "final-estimator-aware-epps-curves-v1.9.csv"

FORBIDDEN_EXACT_PATHS = (
    "functions/coupled_solver.py",
    "functions/dtrw_solver.py",
    "functions/order_book_sources.py",
    "functions/port_audit.py",
    "functions/price_boundary.py",
    "functions/sibuya.py",
    "functions/simulation_state.py",
    "scripts/05_generate_legacy_inputs.py",
    "scripts/06_generate_legacy_target_execution.py",
    "scripts/07_generate_legacy_epps.py",
    "scripts/08_generate_legacy_shock_views.py",
    "scripts/09_run_port_audit.py",
    "config/config-v1.2.json",
    "config/config-v1.7.json",
    "source/source-v0",
)


def _check(identifier: str, claim: str, observed: object, criterion: str, passed: bool) -> dict[str, object]:
    return {
        "check_id": identifier,
        "claim": claim,
        "observed": observed,
        "criterion": criterion,
        "status": "Verified" if passed else "Failed",
        "software_version": "2.0.0",
    }


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    first_image_match = re.search(r"!\[[^\]]*\]\(([^)]+)\)", readme)
    first_image = first_image_match.group(1) if first_image_match else "missing"
    accepted_errors = accepted_input_errors(configuration["accepted_inputs"])

    summary_rows = _rows(SUMMARY_PATH)
    curve_rows = _rows(CURVE_PATH)
    summary = summary_rows[0] if len(summary_rows) == 1 else {}

    archive_paths = set(read_manifest(ARCHIVE_MANIFEST_PATH))
    figure_numbers = {
        int(match.group(1))
        for path in archive_paths
        if (match := re.match(r"figures/figure-(\d{2})-.*\.png$", path))
    }
    expected_figures = set(configuration["public_figure_policy"]["figure_numbers"])
    missing_pairs = [
        path
        for path in configuration["public_figure_policy"].values()
        if isinstance(path, str)
        and path.startswith("figures/")
        and not all((PROJECT_ROOT / Path(path).with_suffix(suffix)).is_file() for suffix in (".pdf", ".png"))
    ]
    forbidden_present = [path for path in FORBIDDEN_EXACT_PATHS if (PROJECT_ROOT / path).exists()]
    legacy_modules = sorted(
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in (PROJECT_ROOT / "functions").rglob("legacy_*.py")
    )
    caches = sorted(
        path for path in archive_paths if "__pycache__" in path or path.endswith(".pyc")
    )
    gate_records = sorted(
        path
        for path in archive_paths
        if path.startswith("ACCEPTANCE-REPORT-") or path.startswith("TEST-REPORT-")
    )
    active_paths = [path for _, path in ACTIVE_STEPS]
    dependence_script = (PROJECT_ROOT / "scripts/35_run_dependence_diagnostics.py").read_text(encoding="utf-8")
    provenance = (PROJECT_ROOT / configuration["bauer_retirement"]["compact_attribution_retained"]).read_text(encoding="utf-8")
    publication = configuration["publication_contract"]

    checks = [
        _check("V2R-01", "accepted v1.9.3 scientific fingerprints", len(accepted_errors), "zero errors", not accepted_errors),
        _check("V2R-02", "sealed v1.9.3 parent identity", configuration["accepted_parent_archive_sha256"], "accepted SHA-256", configuration["accepted_parent_archive_sha256"] == "122ebd1d81a181cd54f6aa827edafa9f18f898eeb2c6756a123a5a9cb5e55f85"),
        _check("V2R-03", "Bauer executable paths removed", forbidden_present, "empty", not forbidden_present),
        _check("V2R-04", "legacy implementation modules removed", legacy_modules, "empty", not legacy_modules),
        _check("V2R-05", "frozen public figure subset", sorted(figure_numbers), "Figures 1 through 11 retained", expected_figures <= figure_numbers),
        _check("V2R-06", "registered public figure pairs", missing_pairs, "all PDF/PNG pairs present", not missing_pairs),
        _check("V2R-07", "README key image", first_image, configuration["public_figure_policy"]["key_readme_figure"], first_image == configuration["public_figure_policy"]["key_readme_figure"]),
        _check("V2R-08", "README development lineage", all(token in readme for token in ("v1.2.x", "v1.7.7", "v1.9.2", "v1.9.3", "v2.0.0")), "complete version lineage present", all(token in readme for token in ("v1.2.x", "v1.7.7", "v1.9.2", "v1.9.3", "v2.0.0"))),
        _check("V2R-09", "boundary representation documented", all(token in readme for token in ("translation", "mode", "$q_j(y)=-a_j\\mu_j y\\exp(-\\mu_j y^2)$", "weak/local", "not as\npointwise equality")), "all correction terms present", all(token in readme for token in ("translation", "mode", "$q_j(y)=-a_j\\mu_j y\\exp(-\\mu_j y^2)$", "weak/local", "not as\npointwise equality"))),
        _check("V2R-10", "compact Bauer attribution retained", len(provenance), "non-executable provenance document", len(provenance) > 1000 and "does not contain or execute" in provenance),
        _check("V2R-11", "Figure 11 path and return diagnostics", all(token in dependence_script for token in ("Uniform-operational log-mid path", "Standardized return distribution", "Normal quantile comparison")), "three explicit panels", all(token in dependence_script for token in ("Uniform-operational log-mid path", "Standardized return distribution", "Normal quantile comparison"))),
        _check("V2R-12", "Figure 11 trade-sign ACF", "Trade-sign autocorrelation in event time" in dependence_script, "explicit panel", "Trade-sign autocorrelation in event time" in dependence_script),
        _check("V2R-13", "Figure 11 price-level ACF excluded", "level autocorrelation is excluded" in dependence_script, "explicit exclusion", "level autocorrelation is excluded" in dependence_script),
        _check("V2R-14", "final curve inventory", len(curve_rows), "20 registered lags", len(curve_rows) == 20),
        _check("V2R-15", "estimator-aware RMSE", summary.get("combined_estimator_aware_rmse"), "0.039719 within 5e-6", abs(float(summary.get("combined_estimator_aware_rmse", "nan")) - 0.039719) <= 5e-6),
        _check("V2R-16", "leading-order RMSE", summary.get("combined_leading_order_product_rmse"), "0.066963 within 5e-6", abs(float(summary.get("combined_leading_order_product_rmse", "nan")) - 0.066963) <= 5e-6),
        _check("V2R-17", "standardized RMSE", summary.get("combined_estimator_aware_standardized_rmse"), "0.455132 within 5e-6", abs(float(summary.get("combined_estimator_aware_standardized_rmse", "nan")) - 0.455132) <= 5e-6),
        _check("V2R-18", "normal-band coverage", summary.get("combined_estimator_aware_coverage"), "1.0", float(summary.get("combined_estimator_aware_coverage", "nan")) == 1.0),
        _check("V2R-19", "no parameter refit", summary.get("parameters_refitted"), "False", summary.get("parameters_refitted") == "False"),
        _check("V2R-20", "single strict entrypoint", configuration["active_route"]["entrypoints"], "scripts/run_all.py only", configuration["active_route"]["entrypoints"] == ["scripts/run_all.py"]),
        _check("V2R-21", "active route complete", len(active_paths), "all registered steps exist", all((PROJECT_ROOT / path).is_file() for path in active_paths)),
        _check("V2R-22", "source-v1 remains frozen", configuration["claim_equivalence"]["no_source_v1_change"], "true", configuration["claim_equivalence"]["no_source_v1_change"] is True),
        _check("V2R-23", "v2 supplement source", (PROJECT_ROOT / "SUPPLEMENTARY-MATERIAL-v2.0.0.tex").is_file(), "present", (PROJECT_ROOT / "SUPPLEMENTARY-MATERIAL-v2.0.0.tex").is_file()),
        _check("V2R-24", "v2 compiled supplement", (PROJECT_ROOT / "supplementary-materials/SUPPLEMENTARY-MATERIAL-v2.0.0.pdf").is_file(), "present", (PROJECT_ROOT / "supplementary-materials/SUPPLEMENTARY-MATERIAL-v2.0.0.pdf").is_file()),
        _check("V2R-25", "no cache or gate-only report files", [*caches, *gate_records], "empty", not caches and not gate_records),
        _check("V2R-26", "GitHub inspection precedes tag", [publication["push_untagged_state_first"], publication["inspect_and_correct_before_tag"]], "both true", publication["push_untagged_state_first"] is True and publication["inspect_and_correct_before_tag"] is True),
        _check("V2R-27", "final release identity", [publication["tag"], publication["release_title"], publication["archive_name"]], "fixed v2.0.0 identity", publication["tag"] == "v2.0.0" and publication["release_title"] == "v2.0.0 — Reproducibility code for arXiv:2606.14182" and publication["archive_name"] == "correlation-emergence-reproducibility-v2.0.0.zip"),
        _check("V2R-28", "release state remains untagged", [publication["repository_state"], publication["tag_created"], publication["github_release_created"]], "untagged candidate; no release", publication["repository_state"] == "untagged_v2.0.0_candidate" and publication["tag_created"] is False and publication["github_release_created"] is False),
    ]

    write_csv(CHECK_PATH, ["check_id", "claim", "observed", "criterion", "status", "software_version"], checks)
    failures = [row for row in checks if row["status"] != "Verified"]
    for row in checks:
        print(f"{row['check_id']}: {row['status']} - {row['claim']}")
    if failures:
        print(f"v2.0.0 release verification failed: {len(failures)} check(s) require attention.")
        return 1
    print("v2.0.0 release verification completed: 28 checks verified, 0 failures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
