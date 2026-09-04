"""Regression tests for the v2.1.0 Figure 13 recovery gate."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from functions.integrity import accepted_input_errors
from functions.stylised_facts import (
    aggregate_book_members,
    curve_difference,
    fixed_histogram,
    fixed_normal_qq,
    histogram_total_variation,
    member_autocorrelations,
    standardize_sample,
)


CONFIG_PATH = ROOT / "config/config-v2.1.0-figure-13.json"
PANEL_CONFIG_DIRECTORY = ROOT / "config/figure-13-panels"
CHECK_PATH = ROOT / "diagnostics/figure-13-stylised-facts-checks-v2.1.csv"
SUMMARY_PATH = ROOT / "outputs/figure-13-summary-v2.1.csv"
SAMPLING_PATH = ROOT / "outputs/figure-13-sampling-audit-v2.1.csv"
STABILITY_PATH = ROOT / "outputs/figure-13-stability-audit-v2.1.csv"
SENSITIVITY_PATH = ROOT / "outputs/figure-13-order-flow-sensitivities-v2.1.csv"
ARCHIVE_PATH = ROOT / "outputs/figure-13-stylised-facts-recovery-v2.1.npz"
PANEL_MANIFEST_PATH = ROOT / "outputs/figure-13-panel-manifest-v2.1.csv"
FIGURE_STEM = ROOT / "figures/figure-13-stylised-facts-recovery-v2"


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _direct_acf(values: np.ndarray, maximum_lag: int) -> np.ndarray:
    sample = np.asarray(values, dtype=float)
    result = np.empty(maximum_lag + 1)
    result[0] = 1.0
    for lag in range(1, maximum_lag + 1):
        left = sample[:-lag] - np.mean(sample[:-lag])
        right = sample[lag:] - np.mean(sample[lag:])
        result[lag] = np.sum(left * right) / np.sqrt(
            np.sum(left * left) * np.sum(right * right)
        )
    return result


class StylisedFactsRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    def test_configuration_and_accepted_boundary(self) -> None:
        self.assertEqual(self.config["schema_version"], "2.1.0")
        self.assertEqual(self.config["accepted_r4_commit"], "f42ae70b239ae3b8c2e6798e8e963e94b82d6561")
        scientific_inputs = [
            record
            for record in self.config["accepted_inputs"]
            if record.get("role") != "doi_bearing_public_readme"
        ]
        self.assertFalse(accepted_input_errors(scientific_inputs))
        self.assertEqual(
            self.config["scientific_boundary"]["row_meaning"],
            ["uniform_operational", "previous_refresh_calendar"],
        )
        self.assertFalse(self.config["scientific_boundary"]["micro_price_constructed"])
        self.assertFalse(self.config["scientific_boundary"]["empirical_row_claimed"])
        self.assertFalse(self.config["scientific_boundary"]["model_parameter_refit"])
        self.assertEqual(
            self.config["accepted_r7a_config_sha256"],
            "a2a86251180b3398834935467d3c9dc901147dfbc6f16ed76e93b8f11250ee03",
        )
        self.assertEqual(self.config["master_experiment"]["event_quantity"], 0.0002)
        self.assertEqual(
            self.config["master_experiment"]["arrival_probability_per_step"], 0.05
        )
        self.assertEqual(
            self.config["distribution"]["histogram_lower_by_domain"], [-6.0, -10.0]
        )
        self.assertEqual(
            self.config["distribution"]["histogram_upper_by_domain"], [6.0, 10.0]
        )

    def test_registered_transformations_on_toy_data(self) -> None:
        sample = np.asarray([-2.0, -1.0, 0.0, 1.0, 2.0])
        standardized, mean, deviation = standardize_sample(sample)
        self.assertEqual(mean, 0.0)
        self.assertAlmostEqual(deviation, np.sqrt(2.5))
        self.assertAlmostEqual(float(np.mean(standardized)), 0.0)
        self.assertAlmostEqual(float(np.var(standardized, ddof=1)), 1.0)
        edges, _, density, _ = fixed_histogram(
            standardized, lower=-3.0, upper=3.0, bins=6
        )
        self.assertAlmostEqual(float(np.sum(density) * (edges[1] - edges[0])), 1.0)
        probabilities, normal, empirical = fixed_normal_qq(
            standardized, lower_probability=0.1, upper_probability=0.9, count=5
        )
        self.assertTrue(np.all(np.diff(probabilities) > 0.0))
        self.assertTrue(np.all(np.diff(normal) > 0.0))
        self.assertTrue(np.all(np.diff(empirical) >= 0.0))
        series = np.stack((sample, -sample), axis=1)[None, :, :]
        members = member_autocorrelations(series, 2)
        path, mean_curve, standard_error = aggregate_book_members(
            np.concatenate((members, members), axis=0)
        )
        self.assertEqual(path.shape, (2, 3))
        self.assertEqual(float(mean_curve[0]), 1.0)
        self.assertEqual(float(standard_error[0]), 0.0)
        self.assertEqual(histogram_total_variation(density, density, edges[1] - edges[0]), 0.0)
        self.assertEqual(curve_difference(mean_curve, mean_curve), (0.0, 0.0))

    def test_generated_checks_and_sampling_gate(self) -> None:
        checks = _rows(CHECK_PATH)
        self.assertGreaterEqual(len(checks), 160)
        self.assertEqual(len({row["check_id"] for row in checks}), len(checks))
        self.assertTrue(all(row["status"] == "Verified" for row in checks))
        sampling = _rows(SAMPLING_PATH)
        self.assertEqual(len(sampling), 12)
        selected = [row for row in sampling if row["selected_for_production"] == "True"]
        self.assertEqual(len(selected), 2)
        self.assertEqual({row["design_id"] for row in selected}, {"extended_both"})
        self.assertEqual({int(row["five_second_return_count"]) for row in selected}, {16928})
        self.assertTrue(
            all(int(row["extreme_tail_count_abs_z_gt_3"]) >= 25 for row in selected)
        )
        self.assertEqual({int(row["terminal_event_margin_steps"]) for row in selected}, {149})

    def test_stability_failures_are_retained_as_extension_triggers(self) -> None:
        rows = _rows(STABILITY_PATH)
        self.assertTrue(rows)
        self.assertEqual({row["status"] for row in rows}, {"Verified"})
        final_rows = [row for row in rows if row["reference_design"] == "extended_both"]
        self.assertTrue(final_rows)
        self.assertTrue(all(row["status"] == "Verified" for row in final_rows))

    def test_summary_states_scientific_differences(self) -> None:
        summary = _rows(SUMMARY_PATH)
        self.assertEqual(len(summary), 1)
        row = summary[0]
        self.assertEqual(row["production_design"], "extended_both")
        self.assertEqual(int(row["paths"]), 16)
        self.assertEqual(int(row["operational_steps"]), 5600)
        self.assertGreaterEqual(int(row["minimum_events_per_path_book"]), 2)
        self.assertEqual(row["return_estimand"], "five_second_log_mid_increment")
        self.assertEqual(row["micro_price_constructed"], "False")
        self.assertEqual(row["empirical_row_claimed"], "False")
        self.assertEqual(row["model_parameter_refit"], "False")
        self.assertEqual(
            row["order_sign_persistence_status"],
            "declared_finite_markov_input_not_endogenous_result",
        )

    def test_archive_recomputes_returns_and_signed_flows(self) -> None:
        with np.load(ARCHIVE_PATH, allow_pickle=False) as archive:
            self.assertEqual(archive["operational_prices"].shape, (16, 5601, 2))
            self.assertEqual(archive["calendar_prices"].shape, (16, 5601, 2))
            self.assertEqual(archive["five_second_log_mid_increments"].shape, (2, 16, 529, 2))
            self.assertEqual(archive["five_second_signed_flows"].shape, (2, 16, 3, 529, 2))
            self.assertEqual(archive["return_autocorrelation_members"].shape, (2, 16, 2, 41))
            self.assertEqual(archive["absolute_return_autocorrelation_members"].shape, (2, 16, 2, 41))
            self.assertEqual(archive["signed_flow_autocorrelation_members"].shape, (2, 3, 16, 2, 41))
            indices = archive["diagnostic_sample_indices"]
            np.testing.assert_allclose(
                archive["five_second_log_mid_increments"][0],
                np.diff(archive["operational_prices"][:, indices, :], axis=1),
                rtol=0.0,
                atol=0.0,
            )
            np.testing.assert_allclose(
                archive["five_second_log_mid_increments"][1],
                np.diff(archive["calendar_prices"][:, indices, :], axis=1),
                rtol=0.0,
                atol=0.0,
            )
            calendar_indices = archive["calendar_operational_indices"]
            query = np.arange(calendar_indices.shape[1])[None, :, None]
            self.assertTrue(np.all(calendar_indices <= query))
            reconstructed_calendar = np.empty_like(archive["calendar_prices"])
            for path in range(16):
                for book in range(2):
                    reconstructed_calendar[path, :, book] = archive[
                        "operational_prices"
                    ][path, calendar_indices[path, :, book], book]
            np.testing.assert_array_equal(
                archive["calendar_prices"], reconstructed_calendar
            )
            signs = archive["declared_ground_truth_signs_by_step"].transpose(0, 2, 1)
            operational_flow = np.cumsum(signs, axis=1)
            expected_operational = np.diff(operational_flow[:, indices, :], axis=1)
            np.testing.assert_array_equal(
                archive["five_second_signed_flows"][0, :, 0], expected_operational
            )
            calendar_flow = np.empty_like(operational_flow)
            for path in range(16):
                for book in range(2):
                    calendar_flow[path, :, book] = operational_flow[
                        path, calendar_indices[path, :, book], book
                    ]
            expected_calendar = np.diff(calendar_flow[:, indices, :], axis=1)
            np.testing.assert_array_equal(
                archive["five_second_signed_flows"][1, :, 0], expected_calendar
            )

    def test_archive_standardization_and_acf_recompute(self) -> None:
        with np.load(ARCHIVE_PATH, allow_pickle=False) as archive:
            for domain in range(2):
                standardized = archive["standardized_returns"][domain]
                self.assertLessEqual(abs(float(np.mean(standardized))), 1e-14)
                self.assertLessEqual(abs(float(np.var(standardized, ddof=1)) - 1.0), 1e-14)
                recomputed = member_autocorrelations(
                    archive["five_second_log_mid_increments"][domain], 40
                )
                np.testing.assert_allclose(
                    recomputed,
                    archive["return_autocorrelation_members"][domain],
                    rtol=0.0,
                    atol=1e-15,
                )

    def test_all_acfs_match_an_independent_formula(self) -> None:
        with np.load(ARCHIVE_PATH, allow_pickle=False) as archive:
            returns = archive["five_second_log_mid_increments"]
            flows = archive["five_second_signed_flows"]
            for domain in range(2):
                for path in range(returns.shape[1]):
                    for book in range(2):
                        np.testing.assert_allclose(
                            archive["return_autocorrelation_members"][domain, path, book],
                            _direct_acf(returns[domain, path, :, book], 40),
                            rtol=0.0,
                            atol=2e-16,
                        )
                        np.testing.assert_allclose(
                            archive["absolute_return_autocorrelation_members"][domain, path, book],
                            _direct_acf(np.abs(returns[domain, path, :, book]), 40),
                            rtol=0.0,
                            atol=2e-16,
                        )
                        for convention in range(flows.shape[2]):
                            np.testing.assert_allclose(
                                archive["signed_flow_autocorrelation_members"][
                                    domain, convention, path, book
                                ],
                                _direct_acf(
                                    flows[domain, path, convention, :, book], 40
                                ),
                                rtol=0.0,
                                atol=2e-16,
                            )

    def test_order_flow_conventions_remain_auditable(self) -> None:
        rows = _rows(SENSITIVITY_PATH)
        self.assertEqual(len(rows), 2 * 3 * 41)
        self.assertEqual({row["sign_convention"] for row in rows}, {
            "ground_truth_aggressor", "quote_midpoint", "legacy_tick_rule"
        })
        self.assertEqual(
            {row["sign_convention"] for row in rows if row["primary_figure_convention"] == "True"},
            {"ground_truth_aggressor"},
        )
        with np.load(ARCHIVE_PATH, allow_pickle=False) as archive:
            arrivals = archive["declared_event_arrivals"]
            declared = archive["declared_ground_truth_signs_by_step"]
            quote = archive["quote_midpoint_signs_by_step"]
            tick = archive["legacy_tick_rule_signs_by_step"]
            self.assertTrue(np.array_equal(declared[arrivals], quote[arrivals]))
            self.assertFalse(np.array_equal(declared[arrivals], tick[arrivals]))

    def test_six_unique_standalone_panel_artifacts(self) -> None:
        manifest = _rows(PANEL_MANIFEST_PATH)
        self.assertEqual(len(manifest), 6)
        self.assertEqual({row["panel_id"] for row in manifest}, set("abcdef"))
        for field in ("source_config", "data_path", "pdf_path", "png_path"):
            self.assertEqual(len({row[field] for row in manifest}), 6)
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
            with Image.open(ROOT / row["png_path"]) as image:
                self.assertEqual(image.size, (1200, 1200))
            reader = PdfReader(str(ROOT / row["pdf_path"]))
            self.assertEqual(len(reader.pages), 1)
            self.assertEqual(round(float(reader.pages[0].mediabox.width)), 288)
            self.assertEqual(round(float(reader.pages[0].mediabox.height)), 288)

    def test_assembly_imports_standalone_pngs(self) -> None:
        r13_manifest = ROOT / "outputs/figure-13-r13-panel-manifest-v2.1.csv"
        if r13_manifest.is_file():
            manifest = _rows(r13_manifest)
            self.assertEqual(len(manifest), 12)
            self.assertEqual({row["panel_id"] for row in manifest}, set("abcdefghijkl"))
            with Image.open(FIGURE_STEM.with_suffix(".png")) as assembled_image:
                self.assertEqual(assembled_image.size, (3960, 4560))
            reader = PdfReader(str(FIGURE_STEM.with_suffix(".pdf")))
            self.assertEqual(len(reader.pages), 1)
            self.assertEqual(round(float(reader.pages[0].mediabox.width)), 950)
            self.assertEqual(round(float(reader.pages[0].mediabox.height)), 1094)
            return
        manifest = _rows(PANEL_MANIFEST_PATH)
        with Image.open(FIGURE_STEM.with_suffix(".png")) as assembled_image:
            assembled = np.asarray(assembled_image.convert("RGB"))
        self.assertEqual(assembled.shape, (2400, 3600, 3))
        for index, row in enumerate(manifest):
            with Image.open(ROOT / row["png_path"]) as panel_image:
                panel = np.asarray(panel_image.convert("RGB"))
            y = (index // 3) * 1200
            x = (index % 3) * 1200
            crop = assembled[y : y + 1200, x : x + 1200]
            np.testing.assert_array_equal(crop[100:, 100:], panel[100:, 100:])
        reader = PdfReader(str(FIGURE_STEM.with_suffix(".pdf")))
        self.assertEqual(len(reader.pages), 1)
        self.assertEqual(round(float(reader.pages[0].mediabox.width)), 864)
        self.assertEqual(round(float(reader.pages[0].mediabox.height)), 576)


if __name__ == "__main__":
    unittest.main()
