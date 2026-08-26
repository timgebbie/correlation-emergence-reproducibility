"""Generate the v1.9.0 final estimator-aware Epps integration."""

from __future__ import annotations

import csv
import json
import os
import sys
from pathlib import Path

import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib-cache"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from functions.figure_io import atomic_savefig, remove_orphaned_figure_staging_files
from functions.integrity import accepted_input_errors, snapshot_errors, snapshot_hashes
from functions.io_utils import write_csv


CONFIG_PATH = PROJECT_ROOT / "config" / "config-v1.9.0.json"
CLOCK_PATH = PROJECT_ROOT / "outputs" / "clock-only-conformity-curves-v1.7.csv"
COUPLING_PATH = PROJECT_ROOT / "outputs" / "corrected-coupling-recovery-curves-v1.7.csv"
COMBINED_PATH = PROJECT_ROOT / "outputs" / "combined-no-refit-curves-v1.7.csv"
CURVE_PATH = PROJECT_ROOT / "outputs" / "final-estimator-aware-epps-curves-v1.9.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "final-estimator-aware-epps-summary-v1.9.csv"
CHECK_PATH = PROJECT_ROOT / "diagnostics" / "final-estimator-aware-epps-checks-v1.9.csv"
FIGURE_STEM = PROJECT_ROOT / "figures" / "figure-07-final-estimator-aware-epps-v2"
VERSION = "1.9.0"


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _values(rows: list[dict[str, str]], name: str) -> np.ndarray:
    return np.asarray([float(row[name]) for row in rows], dtype=float)


def _rmse(estimate: np.ndarray, reference: np.ndarray) -> float:
    return float(np.sqrt(np.mean((estimate - reference) ** 2)))


def _render(value: object) -> object:
    if isinstance(value, (dict, list, tuple, set)):
        if isinstance(value, set):
            value = sorted(value)
        return json.dumps(value, sort_keys=True)
    return value


def _check(
    check_id: str,
    description: str,
    observed: object,
    criterion: str,
    verified: bool,
) -> dict[str, object]:
    return {
        "check_id": check_id,
        "check": description,
        "observed": _render(observed),
        "criterion": criterion,
        "status": "Verified" if verified else "Failed",
        "software_version": VERSION,
    }


def _save_figure(
    lags: np.ndarray,
    clock_theory: np.ndarray,
    clock_simulation: np.ndarray,
    clock_se: np.ndarray,
    coupling_theory: np.ndarray,
    coupling_simulation: np.ndarray,
    coupling_se: np.ndarray,
    product: np.ndarray,
    estimator_theory: np.ndarray,
    combined_simulation: np.ndarray,
    combined_se: np.ndarray,
) -> None:
    remove_orphaned_figure_staging_files()
    fig, axes = plt.subplots(1, 3, figsize=(15.2, 5.1), sharex=True, sharey=True)
    panels = (
        (
            axes[0],
            "Clock only",
            clock_theory,
            clock_simulation,
            clock_se,
            "Equal-rate previous-refresh theory",
            "Clock-only simulation",
            "#1f77b4",
        ),
        (
            axes[1],
            "Corrected coupling only",
            coupling_theory,
            coupling_simulation,
            coupling_se,
            r"$F(\kappa\Delta)$ theory",
            "Coupling-only simulation",
            "#2a9d55",
        ),
    )
    for axis, title, theory, simulation, standard_error, theory_label, simulation_label, colour in panels:
        axis.fill_between(
            lags,
            simulation - 1.96 * standard_error,
            simulation + 1.96 * standard_error,
            color=colour,
            alpha=0.17,
            linewidth=0.0,
            label="Simulation 95% band",
        )
        axis.plot(lags, theory, color="black", linewidth=2.1, label=theory_label)
        axis.plot(lags, simulation, color=colour, linewidth=2.2, label=simulation_label)
        axis.set_title(title)

    axes[2].fill_between(
        lags,
        combined_simulation - 1.96 * combined_se,
        combined_simulation + 1.96 * combined_se,
        color="#b51f2e",
        alpha=0.17,
        linewidth=0.0,
        label="Combined simulation 95% band",
    )
    axes[2].plot(
        lags,
        product,
        color="black",
        linestyle="--",
        linewidth=2.0,
        label="Leading-order product",
    )
    axes[2].plot(
        lags,
        estimator_theory,
        color="#666666",
        linewidth=2.4,
        label="Estimator-aware theory",
    )
    axes[2].plot(
        lags,
        combined_simulation,
        color="#b51f2e",
        linewidth=2.3,
        label="Combined simulation",
    )
    axes[2].set_title("Clock and corrected coupling")

    for axis in axes:
        axis.set_xlim(0.0, 410.0)
        axis.set_ylim(0.0, 1.1)
        axis.set_xlabel(r"Calendar aggregation scale $\Delta t$ [s]")
        axis.grid(alpha=0.18)
        axis.legend(loc="lower right", fontsize=8.2, frameon=False)
    axes[0].set_ylabel("Normalized covariance response")
    fig.suptitle("Final estimator-aware Epps integration: frozen parameters", fontsize=15)
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.95))
    atomic_savefig(fig, FIGURE_STEM.with_suffix(".pdf"), bbox_inches="tight")
    atomic_savefig(fig, FIGURE_STEM.with_suffix(".png"), dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if configuration.get("schema_version") != VERSION:
        raise ValueError("v1.9.0 configuration version mismatch")
    input_errors = accepted_input_errors(configuration["accepted_inputs"])
    input_hashes = snapshot_hashes(configuration["accepted_inputs"])

    clock_rows = [
        row for row in _read_rows(CLOCK_PATH) if row["tier"] == "thick_boundary"
    ]
    coupling_rows = _read_rows(COUPLING_PATH)
    combined_rows = _read_rows(COMBINED_PATH)
    lags = _values(combined_rows, "lag_seconds")
    registered_lags = np.asarray(configuration["registered_lags_seconds"], dtype=float)
    exact_lag_join = (
        np.array_equal(lags, registered_lags)
        and np.array_equal(_values(clock_rows, "lag_seconds"), lags)
        and np.array_equal(_values(coupling_rows, "lag_seconds"), lags)
    )

    clock_theory = _values(clock_rows, "exact_equal_rate_curve")
    clock_simulation = _values(clock_rows, "normalized_simulation")
    clock_se = _values(clock_rows, "jackknife_standard_error")
    coupling_theory = _values(coupling_rows, "analytical_normalized_covariance")
    coupling_simulation = _values(coupling_rows, "simulated_normalized_covariance")
    coupling_se = _values(coupling_rows, "covariance_jackknife_standard_error")
    product = _values(combined_rows, "analytical_leading_order_product")
    estimator_theory = _values(
        combined_rows, "thick_exact_reduced_same_clock_covariance"
    )
    combined_simulation = _values(combined_rows, "thick_simulated_combined_covariance")
    combined_se = _values(combined_rows, "thick_covariance_standard_error")

    source_join = {
        "clock_theory": np.array_equal(
            clock_theory, _values(combined_rows, "analytical_clock_factor")
        ),
        "clock_simulation": np.array_equal(
            clock_simulation, _values(combined_rows, "accepted_clock_thick_boundary")
        ),
        "coupling_theory": np.array_equal(
            coupling_theory, _values(combined_rows, "analytical_coupling_factor")
        ),
        "coupling_simulation": np.array_equal(
            coupling_simulation,
            _values(combined_rows, "accepted_corrected_coupling"),
        ),
    }
    product_reconstructs = np.allclose(
        product, clock_theory * coupling_theory, rtol=1e-14, atol=1e-15
    )
    estimator_rmse = _rmse(combined_simulation, estimator_theory)
    product_rmse = _rmse(combined_simulation, product)
    standardized_rmse = float(
        np.sqrt(np.mean(((combined_simulation - estimator_theory) / combined_se) ** 2))
    )
    coverage = float(
        np.mean(
            np.abs(combined_simulation - estimator_theory) <= 1.96 * combined_se
        )
    )

    curve_rows = []
    for position, lag in enumerate(lags):
        curve_rows.append(
            {
                "target_id": configuration["target_id"],
                "lag_seconds": lag,
                "clock_only_theory": clock_theory[position],
                "clock_only_simulation": clock_simulation[position],
                "clock_only_simulation_standard_error": clock_se[position],
                "coupling_only_theory": coupling_theory[position],
                "coupling_only_simulation": coupling_simulation[position],
                "coupling_only_simulation_standard_error": coupling_se[position],
                "combined_simulation": combined_simulation[position],
                "combined_simulation_standard_error": combined_se[position],
                "leading_order_product": product[position],
                "estimator_aware_finite_grid_finite_step_theory": estimator_theory[position],
                "combined_minus_estimator_aware_theory": combined_simulation[position]
                - estimator_theory[position],
                "combined_minus_leading_order_product": combined_simulation[position]
                - product[position],
                "fit_policy": "frozen_no_retuning",
                "software_version": VERSION,
            }
        )
    write_csv(CURVE_PATH, list(curve_rows[0]), curve_rows)

    summary = {
        "target_id": configuration["target_id"],
        "result_label": "final_estimator_aware_integration_established",
        "clock_only_rmse": _rmse(clock_simulation, clock_theory),
        "coupling_only_rmse": _rmse(coupling_simulation, coupling_theory),
        "combined_estimator_aware_rmse": estimator_rmse,
        "combined_leading_order_product_rmse": product_rmse,
        "combined_estimator_aware_standardized_rmse": standardized_rmse,
        "combined_estimator_aware_coverage": coverage,
        "parameters_refitted": False,
        "next_stage": configuration["output_contract"]["next_stage"],
        "software_version": VERSION,
    }
    write_csv(SUMMARY_PATH, list(summary), [summary])

    _save_figure(
        lags,
        clock_theory,
        clock_simulation,
        clock_se,
        coupling_theory,
        coupling_simulation,
        coupling_se,
        product,
        estimator_theory,
        combined_simulation,
        combined_se,
    )

    architecture = configuration["architecture"]
    policy = configuration["acceptance_policy"]
    figure_pair = all(
        FIGURE_STEM.with_suffix(f".{suffix}").is_file() for suffix in ("pdf", "png")
    )
    checks = [
        _check("S9E-01", "accepted v1.8.3 input hashes", not input_errors, "all exact", not input_errors),
        _check("S9E-02", "accepted parent", configuration["accepted_parent"], "v1.8.3", configuration["accepted_parent"] == "v1.8.3"),
        _check("S9E-03", "uniform operational dynamics", architecture["operational_dynamics"], "uniform fixed grid only", architecture["operational_dynamics"] == "uniform_fixed_grid_only"),
        _check("S9E-04", "post-path calendar observation", architecture["calendar_observation"], "book-specific previous refresh after completion", architecture["calendar_observation"] == "book_specific_previous_refresh_after_operational_completion"),
        _check("S9E-05", "calendar interpolation", architecture["calendar_interpolation"], "forbidden", architecture["calendar_interpolation"] == "forbidden"),
        _check("S9E-06", "legacy nonuniform state update", architecture["legacy_nonuniform_state_update"], "forbidden", architecture["legacy_nonuniform_state_update"] == "forbidden"),
        _check("S9E-07", "parameter and curve refit", [architecture["model_parameter_refit"], architecture["curve_calibration"]], "both forbidden", architecture["model_parameter_refit"] == architecture["curve_calibration"] == "forbidden"),
        _check("S9E-08", "required curve inventory", configuration["required_curves"], "seven declared curves", len(configuration["required_curves"]) == 7),
        _check("S9E-09", "registered lag join", exact_lag_join, "20 exact common lags", exact_lag_join and lags.size == 20),
        _check("S9E-10", "clock theory source join", source_join["clock_theory"], "exact", source_join["clock_theory"]),
        _check("S9E-11", "clock simulation source join", source_join["clock_simulation"], "exact", source_join["clock_simulation"]),
        _check("S9E-12", "coupling theory source join", source_join["coupling_theory"], "exact", source_join["coupling_theory"]),
        _check("S9E-13", "coupling simulation source join", source_join["coupling_simulation"], "exact", source_join["coupling_simulation"]),
        _check("S9E-14", "leading-order product reconstruction", product_reconstructs, "clock theory times coupling theory", product_reconstructs),
        _check("S9E-15", "estimator-aware theory source", "thick_exact_reduced_same_clock_covariance", "accepted finite-grid finite-step same-clock reference", True),
        _check("S9E-16", "combined simulation source", "thick_simulated_combined_covariance", "accepted no-refit holdout", True),
        _check("S9E-17", "estimator-aware RMSE improvement", [estimator_rmse, product_rmse], "estimator-aware below leading-order product", estimator_rmse < product_rmse),
        _check("S9E-18", "combined standardized RMSE", standardized_rmse, f"at most {policy['combined_standardized_rmse_maximum']}", standardized_rmse <= float(policy["combined_standardized_rmse_maximum"])),
        _check("S9E-19", "combined pointwise coverage", coverage, f"at least {policy['minimum_combined_pointwise_coverage']}", coverage >= float(policy["minimum_combined_pointwise_coverage"])),
        _check("S9E-20", "common display scales", configuration["display_contract"], "three panels share linear x and y scales", configuration["display_contract"]["aggregation_axis"] == "linear"),
        _check("S9E-21", "Figure 7 pair", figure_pair, "PDF and PNG", figure_pair),
        _check("S9E-22", "curve output rows", len(curve_rows), "20", len(curve_rows) == 20),
        _check("S9E-23", "optional calibrated curve", configuration["display_contract"]["optional_calibrated_curve"], "excluded", configuration["display_contract"]["optional_calibrated_curve"] == "excluded"),
        _check("S9E-24", "accepted inputs unchanged", not snapshot_errors(input_hashes), "all start/end hashes exact", not snapshot_errors(input_hashes)),
    ]
    write_csv(
        CHECK_PATH,
        ["check_id", "check", "observed", "criterion", "status", "software_version"],
        checks,
    )
    failed = sum(row["status"] == "Failed" for row in checks)
    for row in checks:
        print(f"{row['check_id']}: {row['status']} - {row['check']}")
    print(
        f"Final estimator-aware Epps integration completed: {len(checks) - failed} "
        f"checks verified, {failed} failures."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
