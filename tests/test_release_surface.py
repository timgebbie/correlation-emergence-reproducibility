"""Focused tests for the untagged v2.0.0 public release surface."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import unittest
from pathlib import Path

from functions.integrity import ARCHIVE_MANIFEST_PATH, read_manifest
from scripts.run_all import ACTIVE_STEPS, _parse_args


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "config-v2.0.0.json"


class ReleaseSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_parent_and_source_identity(self) -> None:
        self.assertEqual(self.config["accepted_parent"], "v1.9.3")
        self.assertEqual(
            self.config["accepted_parent_archive_sha256"],
            "122ebd1d81a181cd54f6aa827edafa9f18f898eeb2c6756a123a5a9cb5e55f85",
        )
        source = ROOT / "source/source-v1/CATG-RD2Epps-v3-arXiv.tex"
        self.assertEqual(
            hashlib.sha256(source.read_bytes()).hexdigest(),
            "48eea98a6fb084d6ecc397bede4c107a44cae947e16271d66a7041e2997afb5a",
        )

    def test_bauer_executable_surface_is_absent(self) -> None:
        self.assertFalse((ROOT / "source/source-v0").exists())
        self.assertFalse(list((ROOT / "functions").rglob("legacy_*.py")))
        for path in (
            "scripts/05_generate_legacy_inputs.py",
            "scripts/06_generate_legacy_target_execution.py",
            "scripts/07_generate_legacy_epps.py",
            "scripts/08_generate_legacy_shock_views.py",
            "scripts/09_run_port_audit.py",
        ):
            self.assertFalse((ROOT / path).exists(), path)

    def test_compact_scientific_attribution_remains(self) -> None:
        path = ROOT / "provenance/BAUER-ANTECEDENT-AND-CORRECTIONS-v2.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("uniform operational grid", text)
        self.assertIn("exp(-mu*y^2)", text)
        self.assertIn("translation mode", text)
        self.assertIn("pointwise kernel identity", text)

    def test_readme_first_image_is_final_figure_7(self) -> None:
        match = re.search(r"!\[[^\]]*\]\(([^)]+)\)", self.readme)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "figures/figure-07-final-estimator-aware-epps-v2.png")

    def test_public_figure_sequence_is_exact(self) -> None:
        archive_paths = set(read_manifest(ARCHIVE_MANIFEST_PATH))
        numbers = {
            int(match.group(1))
            for path in archive_paths
            if (match := re.match(r"figures/figure-(\d{2})-.*\.png$", path))
        }
        self.assertEqual(numbers, set(range(1, 12)))

    def test_single_trade_and_meta_order_figures_are_retained(self) -> None:
        for stem in (
            "figures/figure-09-single-trade-impact-v2",
            "figures/figure-10-meta-order-impact-v2",
        ):
            self.assertGreater((ROOT / f"{stem}.png").stat().st_size, 1000)
            self.assertGreater((ROOT / f"{stem}.pdf").stat().st_size, 1000)

    def test_figure_11_contains_both_requested_autocorrelations(self) -> None:
        script = (ROOT / "scripts/35_run_dependence_diagnostics.py").read_text(encoding="utf-8")
        self.assertIn("Log-mid increment autocorrelation", script)
        self.assertIn("Trade-sign autocorrelation in event time", script)
        self.assertIn("Subordinated signed-flow autocorrelation", script)
        self.assertIn("level autocorrelation is excluded", script)

    def test_final_metrics_are_unchanged(self) -> None:
        with (ROOT / "outputs/final-estimator-aware-epps-summary-v1.9.csv").open(
            "r", encoding="utf-8", newline=""
        ) as handle:
            row = list(csv.DictReader(handle))[0]
        self.assertAlmostEqual(float(row["combined_estimator_aware_rmse"]), 0.039719, places=5)
        self.assertAlmostEqual(float(row["combined_leading_order_product_rmse"]), 0.066963, places=5)
        self.assertAlmostEqual(float(row["combined_estimator_aware_standardized_rmse"]), 0.455132, places=5)
        self.assertEqual(float(row["combined_estimator_aware_coverage"]), 1.0)
        self.assertEqual(row["parameters_refitted"], "False")

    def test_readme_contains_complete_development_lineage(self) -> None:
        for token in ("v1.0.0", "v1.2.x", "v1.7.7", "v1.8.3", "v1.9.2", "v1.9.3", "v2.0.0"):
            self.assertIn(token, self.readme)

    def test_readme_and_provenance_explain_boundary_correction(self) -> None:
        self.assertIn("-d(phi)/dx", self.readme)
        self.assertIn("weak/local", self.readme)
        self.assertIn("not pointwise equality", self.readme)
        self.assertIn("exp(-mu*y^2)", self.readme)

    def test_single_entrypoint_supports_strict_and_rerun(self) -> None:
        self.assertEqual(self.config["active_route"]["entrypoints"], ["scripts/run_all.py"])
        self.assertFalse(_parse_args([]).rerun)
        self.assertTrue(_parse_args(["--rerun"]).rerun)
        self.assertTrue(all((ROOT / path).is_file() for _, path in ACTIVE_STEPS))

    def test_publication_remains_deferred_until_inspection(self) -> None:
        publication = self.config["publication_contract"]
        self.assertTrue(publication["push_untagged_state_first"])
        self.assertTrue(publication["inspect_and_correct_before_tag"])
        self.assertEqual(publication["repository_state"], "untagged_v2.0.0_candidate")
        self.assertFalse(publication["tag_created"])
        self.assertFalse(publication["github_release_created"])
        self.assertEqual(publication["tag"], "v2.0.0")
        self.assertTrue(publication["release_title"].startswith("v2.0.0 — "))
        self.assertFalse((ROOT / "ACCEPTANCE-REPORT-v1.9.3.md").exists())
        self.assertFalse((ROOT / "TEST-REPORT-v1.9.3.md").exists())


if __name__ == "__main__":
    unittest.main()
