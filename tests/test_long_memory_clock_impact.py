"""Regression tests for the v2.1.0 long-memory clock and impact extension."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import unittest

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config/config-v2.1.0-clock-impact.json"
CHECK_PATH = ROOT / "diagnostics/clock-impact-science-math-checks-v2.1.csv"
FIG13_ARCHIVE = ROOT / "outputs/figure-13-long-memory-clock-comparison-v2.1.npz"
IMPACT_ARCHIVE = ROOT / "outputs/clock-subordinated-impact-v2.1.npz"
CURVE_PATH = ROOT / "outputs/clock-subordinated-impact-curves-v2.1.csv"
PANEL_MANIFEST = ROOT / "outputs/figure-13-observation-clock-panel-manifest-v2.1.csv"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class LongMemoryClockImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_registered_scope(self) -> None:
        self.assertEqual(self.config["schema_version"], "2.1.0")
        self.assertEqual(self.config["target_id"], "V210-CLOCK-IMPACT")
        rows = self.config["figure_13"]["rows"]
        self.assertEqual([row["clock"] for row in rows], [
            "none", "poisson", "mittag_leffler", "tempered_mittag_leffler"
        ])
        self.assertEqual(rows[2]["beta"], 0.8)
        self.assertEqual(rows[3]["tempering_rate_per_second"], 0.0125)
        self.assertFalse(self.config["scientific_boundary"]["parameter_refit"])

    def test_science_math_register(self) -> None:
        rows = _rows(CHECK_PATH)
        self.assertEqual(len(rows), 20)
        self.assertEqual(len({row["check_id"] for row in rows}), 20)
        self.assertTrue(all(row["status"] == "Verified" for row in rows))

    def test_figure13_previous_refresh_and_clock_morphology(self) -> None:
        with np.load(FIG13_ARCHIVE, allow_pickle=False) as archive:
            self.assertEqual(archive["prices"].shape, (4, 16, 5601, 2))
            self.assertEqual(archive["returns"].shape, (4, 16, 529, 2))
            operational = archive["prices"][0]
            indices = archive["operational_indices"]
            for domain in range(4):
                for path in range(16):
                    for book in range(2):
                        np.testing.assert_array_equal(
                            archive["prices"][domain, path, :, book],
                            operational[path, indices[domain, path, :, book], book],
                        )
            zero = np.mean(np.isclose(archive["returns"], 0.0), axis=(1, 2, 3))
            np.testing.assert_allclose(
                zero, [0.0, 0.6049149338374291, 0.8819116257088847, 0.6610349716446124],
                rtol=0.0, atol=1e-15,
            )
            self.assertGreater(float(archive["order_flow_acf_mean"][0, 10]), 0.02)

    def test_impact_archive_and_curves(self) -> None:
        with np.load(IMPACT_ARCHIVE, allow_pickle=False) as archive:
            self.assertEqual(archive["single_responses"].shape, (8, 2, 2, 4, 12, 2))
            self.assertEqual(archive["meta_trajectory"].shape, (2, 8, 2, 2, 4, 4, 2))
            self.assertEqual(archive["meta_relaxation"].shape, (2, 8, 2, 2, 4, 9, 2))
            for key in ("single_responses", "meta_trajectory", "meta_relaxation"):
                self.assertTrue(np.all(np.isfinite(archive[key])))
            self.assertTrue(np.all(archive["single_active"] >= 0.0))
            self.assertTrue(np.all(archive["single_active"] <= 1.0))
        rows = _rows(CURVE_PATH)
        self.assertEqual(
            {row["measurement_domain"] for row in rows},
            {
                "operational_gaussian",
                "poisson_previous_refresh",
                "mittag_leffler_previous_refresh",
                "tempered_mittag_leffler_previous_refresh",
            },
        )
        self.assertEqual(
            {row["experiment"] for row in rows},
            {"single_trade", "meta_order_trajectory", "meta_order_relaxation"},
        )

    def test_figures_and_panel_manifest(self) -> None:
        with Image.open(ROOT / "figures/figure-13-stylised-facts-recovery-v2.png") as image:
            self.assertEqual(image.size, (3960, 4560))
        with Image.open(ROOT / "figures/figure-14-clock-subordinated-impact-v2.png") as image:
            self.assertEqual(image.size, (3600, 2580))
        manifest = _rows(PANEL_MANIFEST)
        self.assertEqual(len(manifest), 12)
        self.assertEqual({row["panel_id"] for row in manifest}, set("abcdefghijkl"))
        for row in manifest:
            for path_field, hash_field in (
                ("source_config", "source_config_sha256"),
                ("data_path", "data_sha256"),
                ("pdf_path", "pdf_sha256"),
                ("png_path", "png_sha256"),
            ):
                path = ROOT / row[path_field]
                self.assertTrue(path.is_file())
                self.assertEqual(_sha256(path), row[hash_field])

    def test_supplement_algorithm_boundary(self) -> None:
        root = (ROOT / "SUPPLEMENTARY-MATERIAL-v2.1.0.tex").read_text(encoding="utf-8")
        algorithms = (ROOT / "source/source-v2/NUMERICAL-ALGORITHMS-v2.1.tex").read_text(encoding="utf-8")
        science = (ROOT / "source/source-v2/LONG-MEMORY-CLOCK-IMPACT-v2.1.tex").read_text(encoding="utf-8")
        normalized_algorithms = " ".join(algorithms.split())
        self.assertIn("LONG-MEMORY-CLOCK-IMPACT-v2.1.tex", root)
        self.assertIn("alg:renewal-clock-construction", algorithms)
        self.assertIn("alg:paired-clock-impact", algorithms)
        self.assertIn("same realised clock", normalized_algorithms)
        self.assertIn("shocked-minus-control", science)


if __name__ == "__main__":
    unittest.main()
