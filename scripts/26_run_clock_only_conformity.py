"""Run the v1.7.4 clock-only theory/estimator conformity gate."""

from __future__ import annotations

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

from functions.correlation_build_up import ordinary_build_up
from functions.figure_io import atomic_savefig, remove_orphaned_figure_staging_files
from functions.io_utils import write_csv
from functions.observation import (
    overlap_component_sums,
    poisson_refresh_path_from_uniforms,
    pooled_correlation_summary,
    return_component_sums,
    subordinate_two_book_previous_refresh,
)
from functions.operational import (
    OperationalSolverSpec,
    OperationalSource,
    TwoBookInnovationPolicy,
    apply_spatial_boundary,
    operational_sibuya_kernel,
    operational_source_density,
    operational_two_book_ensemble,
    stationary_density,
)


CONFIG_PATH = PROJECT_ROOT / "config" / "config-v1.7.4.json"
CHECK_PATH = PROJECT_ROOT / "diagnostics" / "clock-only-conformity-checks-v1.7.csv"
CURVE_PATH = PROJECT_ROOT / "outputs" / "clock-only-conformity-curves-v1.7.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "clock-only-conformity-summary-v1.7.csv"
BOUNDARY_PATH = PROJECT_ROOT / "outputs" / "clock-only-boundary-paths-v1.7.npz"
FIGURE_STEM = PROJECT_ROOT / "figures" / "figure-19-clock-only-conformity-v1"
VERSION = "1.7.4"


def _load_configuration() -> dict[str, object]:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        configuration = json.load(handle)
    if configuration.get("schema_version") != VERSION:
        raise ValueError("clock-only conformity configuration version mismatch")
    if configuration["architecture"]["operational_dynamics"] != "uniform_fixed_grid_only":
        raise ValueError("v1.7.4 must preserve uniform operational dynamics")
    return configuration


def _exact_correlation_normals(
    paths: int,
    steps: int,
    correlation: float,
    seed: int,
) -> np.ndarray:
    """Generate externally owned standard normals with exact pooled moments."""

    values = np.random.default_rng(seed).standard_normal((paths, steps, 2))
    first = values[..., 0].reshape(-1)
    residual = values[..., 1].reshape(-1)
    first -= np.mean(first)
    residual -= np.mean(residual)
    first *= np.sqrt(first.size / np.sum(first**2))
    residual -= first * np.dot(first, residual) / np.dot(first, first)
    residual *= np.sqrt(residual.size / np.sum(residual**2))
    second = correlation * first + np.sqrt(1.0 - correlation**2) * residual
    values[..., 0] = first.reshape(paths, steps)
    values[..., 1] = second.reshape(paths, steps)
    return values


def _refresh_pairs(
    groups: int,
    replications: int,
    rates: tuple[float, float],
    horizon: float,
    draws: int,
    seed: int,
    prefix: str,
):
    rng = np.random.default_rng(seed)
    uniforms = rng.random((groups, replications, 2, draws))
    lower = np.nextafter(0.0, 1.0)
    upper = np.nextafter(1.0, 0.0)
    uniforms = np.clip(uniforms, lower, upper)
    result = []
    for group in range(groups):
        replications_result = []
        for replication in range(replications):
            books = tuple(
                poisson_refresh_path_from_uniforms(
                    uniforms[group, replication, book],
                    rates[book],
                    horizon,
                    stream_id=(
                        f"{prefix}-G{group:03d}-R{replication:02d}-B{book + 1}"
                    ),
                )
                for book in range(2)
            )
            replications_result.append(books)
        result.append(tuple(replications_result))
    return tuple(result)


def _measured_rates(refresh_pairs) -> np.ndarray:
    counts = np.zeros(2, dtype=float)
    total_waits = np.zeros(2, dtype=float)
    for group in refresh_pairs:
        for replication in group:
            for book, path in enumerate(replication):
                counts[book] += path.waiting_intervals.size
                total_waits[book] += np.sum(path.waiting_intervals)
    return counts / total_waits


def _brownian_prices(
    paths: int,
    steps: int,
    step_seconds: float,
    correlation: float,
    innovation_scale: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    normals = _exact_correlation_normals(paths, steps, correlation, seed)
    increments = innovation_scale * np.sqrt(step_seconds) * normals
    prices = np.concatenate(
        (np.zeros((paths, 1, 2)), np.cumsum(increments, axis=1)), axis=1
    )
    operational_times = step_seconds * np.arange(steps + 1, dtype=float)
    measured = float(np.corrcoef(normals[..., 0].ravel(), normals[..., 1].ravel())[0, 1])
    return operational_times, prices, measured


def _clocked_component_groups(
    operational_times: np.ndarray,
    prices: np.ndarray,
    refresh_pairs,
    query_times: np.ndarray,
    lag_steps: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, int]:
    groups = prices.shape[0]
    if len(refresh_pairs) != groups:
        raise ValueError("refresh groups and operational paths must agree")
    return_components = np.zeros((groups, lag_steps.size, 3), dtype=float)
    overlap_components = np.zeros_like(return_components)
    maximum_index = 0
    operational_step = float(operational_times[1] - operational_times[0])
    for group in range(groups):
        for paths in refresh_pairs[group]:
            result = subordinate_two_book_previous_refresh(
                operational_times,
                prices[group],
                paths,
                query_times,
            )
            return_components[group] += return_component_sums(
                result.prices, lag_steps
            )
            overlap_components[group] += overlap_component_sums(
                result.operational_indices,
                lag_steps,
                operational_step=operational_step,
            )
            maximum_index = max(maximum_index, int(np.max(result.operational_indices)))
    return return_components, overlap_components, maximum_index


def _operational_model(configuration: dict[str, object]):
    grid = np.linspace(-10.0, 10.0, 201)
    delta_x = float(grid[1] - grid[0])
    diffusion = (0.5, 0.5)
    transport_probability = 0.5
    operational_orders = (1.0, 1.0)
    delta_u = transport_probability * delta_x**2 / (2.0 * diffusion[0])
    requested_delta = float(configuration["time_resolution"]["operational_step_model_units"])
    if not np.isclose(delta_u, requested_delta, rtol=1e-13, atol=1e-15):
        raise ValueError("v1.7.4 grid does not produce the registered operational step")
    sources = (OperationalSource(1.0, 0.1), OperationalSource(1.0, 0.1))
    initial = np.stack(
        [
            apply_spatial_boundary(
                stationary_density(
                    grid,
                    np.asarray(operational_source_density(grid, 0.0, sources[book])),
                    diffusion=diffusion[book],
                    cancellation_rate=0.0,
                    boundary_condition="dirichlet_zero",
                )
            )
            for book in range(2)
        ]
    )
    kernels = tuple(operational_sibuya_kernel(order, 1) for order in operational_orders)
    specification = OperationalSolverSpec(
        delta_u=delta_u,
        transport_probability=transport_probability,
        cancellation_rates=(0.0, 0.0),
        minimum_abs_boundary_slope=1e-6,
    )
    return grid, diffusion, sources, initial, kernels, specification


def _boundary_ensemble(
    configuration: dict[str, object],
    paths: int,
    steps: int,
    seed: int,
):
    grid, diffusion, sources, initial, kernels, specification = _operational_model(
        configuration
    )
    boundary = configuration["thick_boundary"]
    correlation = float(boundary["operational_correlation"])
    # The policy applies the declared cross-book correlation.  Its supplied
    # base streams must therefore be orthogonal rather than pre-correlated.
    base = _exact_correlation_normals(paths, steps, 0.0, seed)
    policy = TwoBookInnovationPolicy(
        float(boundary["innovation_sigma"][0]),
        float(boundary["innovation_sigma"][1]),
        correlation,
    )
    result = operational_two_book_ensemble(
        grid,
        initial,
        (0.0, 0.0),
        sources,
        ((None, None), (None, None)),
        kernels,
        base,
        policy,
        diffusion,
        specification,
    )
    measured = float(
        np.corrcoef(
            result.correlated_standard_normals[..., 0].ravel(),
            result.correlated_standard_normals[..., 1].ravel(),
        )[0, 1]
    )
    return result, measured


def _identity_component_groups(
    prices: np.ndarray,
    query_indices: np.ndarray,
    lag_steps: np.ndarray,
) -> np.ndarray:
    return np.stack(
        [return_component_sums(path[query_indices], lag_steps) for path in prices]
    )


def _curve_metrics(curve: np.ndarray, standard_error: np.ndarray, theory: np.ndarray):
    residual = curve - theory
    rmse = float(np.sqrt(np.mean(residual**2)))
    standardized = float(np.sqrt(np.mean((residual / standard_error) ** 2)))
    coverage = float(np.mean(np.abs(residual) <= 1.96 * standard_error))
    first_band = float(np.mean(curve[-10:-5]))
    second_band = float(np.mean(curve[-5:]))
    plateau_shift = abs(second_band - first_band) / abs(second_band)
    return rmse, standardized, coverage, plateau_shift


def _check(
    check_id: str,
    check: str,
    observed,
    criterion: str,
    passed: bool,
    *,
    qualification_allowed: bool = False,
) -> dict[str, object]:
    if passed:
        status = "Verified"
    elif qualification_allowed:
        status = "Qualified"
    else:
        status = "Failed"
    return {
        "check_id": check_id,
        "check": check,
        "observed": observed,
        "criterion": criterion,
        "status": status,
        "software_version": VERSION,
    }


def _plot(
    lags_seconds: np.ndarray,
    theory: np.ndarray,
    old_pooled: np.ndarray,
    reduced: np.ndarray,
    reduced_se: np.ndarray,
    reduced_overlap: np.ndarray,
    boundary: np.ndarray,
    boundary_se: np.ndarray,
    boundary_overlap: np.ndarray,
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(11.0, 7.8), sharex="col")
    specifications = (
        (axes[0, 0], reduced, reduced_se, reduced_overlap, "Reduced correlated-Brownian reference"),
        (axes[0, 1], boundary, boundary_se, boundary_overlap, "Uncoupled thick-boundary benchmark"),
    )
    for axis, estimate, standard_error, overlap, title in specifications:
        axis.fill_between(
            lags_seconds,
            estimate - 1.96 * standard_error,
            estimate + 1.96 * standard_error,
            color="#2166ac",
            alpha=0.17,
            label="Pooled estimate 95% jackknife band",
        )
        axis.plot(lags_seconds, theory, color="#111111", lw=2.0, label=r"Exact equal-rate $F(\lambda\Delta t)$")
        axis.plot(lags_seconds, estimate, color="#2166ac", lw=1.7, label="Simulation / identity reference")
        axis.plot(lags_seconds, overlap, color="#1b7837", lw=1.2, ls="--", label="Realised exact interval overlap")
        axis.plot(lags_seconds, old_pooled, color="#b2182b", lw=1.0, ls=":", label="Old pooled-rate envelope")
        axis.set_ylim(0.45, 1.08)
        axis.set_title(title)
        axis.grid(alpha=0.18, linewidth=0.5)
    axes[0, 0].set_ylabel("Normalised realised correlation")
    axes[0, 0].legend(frameon=False, fontsize=7.6, loc="lower right")
    for axis, estimate, standard_error in (
        (axes[1, 0], reduced, reduced_se),
        (axes[1, 1], boundary, boundary_se),
    ):
        residual = estimate - theory
        axis.fill_between(
            lags_seconds,
            -1.96 * standard_error,
            1.96 * standard_error,
            color="#999999",
            alpha=0.18,
            label="Zero-centred 95% band",
        )
        axis.plot(lags_seconds, residual, color="#5e3c99", lw=1.5)
        axis.axhline(0.0, color="black", lw=0.7)
        axis.set_xlabel(r"Calendar aggregation scale $\Delta t$ [s]")
        axis.grid(alpha=0.18, linewidth=0.5)
    axes[1, 0].set_ylabel("Simulation minus exact theory")
    figure.suptitle("Clock-only conformity after the equal-rate correction")
    figure.subplots_adjust(left=0.08, right=0.98, bottom=0.09, top=0.92, wspace=0.18, hspace=0.18)
    metadata = {
        "Creator": "correlation-emergence-v1.7.4",
        "CreationDate": None,
        "ModDate": None,
    }
    atomic_savefig(figure, FIGURE_STEM.with_suffix(".pdf"), metadata=metadata)
    atomic_savefig(figure, FIGURE_STEM.with_suffix(".png"), dpi=200)
    plt.close(figure)


def main() -> int:
    remove_orphaned_figure_staging_files()
    configuration = _load_configuration()
    time = configuration["time_resolution"]
    correction = configuration["theory_rate_correction"]
    reduced_config = configuration["reduced_reference"]
    boundary_config = configuration["thick_boundary"]
    policy = configuration["acceptance_policy"]
    step_seconds = float(time["operational_step_seconds"])
    boundary_steps = int(time["total_operational_steps"])
    boundary_total_horizon = float(time["total_horizon_seconds"])
    boundary_warm_up = float(time["warm_up_seconds"])
    boundary_analysis_horizon = float(time["analysis_horizon_seconds"])
    reduced_steps = int(reduced_config["total_operational_steps"])
    reduced_total_horizon = float(reduced_config["total_horizon_seconds"])
    reduced_warm_up = float(reduced_config["warm_up_seconds"])
    reduced_analysis_horizon = float(reduced_config["analysis_horizon_seconds"])
    lags_seconds = np.asarray(configuration["registered_comparison_lags_seconds"], dtype=float)
    lag_steps = np.rint(lags_seconds / step_seconds).astype(int)
    reduced_query_times = reduced_warm_up + step_seconds * np.arange(
        int(round(reduced_analysis_horizon / step_seconds)) + 1, dtype=float
    )
    boundary_query_times = boundary_warm_up + step_seconds * np.arange(
        int(round(boundary_analysis_horizon / step_seconds)) + 1, dtype=float
    )
    boundary_query_indices = np.rint(boundary_query_times / step_seconds).astype(int)
    rates = tuple(float(value) for value in correction["equal_book_refresh_rates_per_second"])
    displayed_rate = float(correction["displayed_clock_rate_per_second"])
    pooled_rate = float(correction["pooled_minimum_wait_rate_per_second"])
    theory = np.asarray(ordinary_build_up(displayed_rate * lags_seconds), dtype=float)
    old_pooled = np.asarray(ordinary_build_up(pooled_rate * lags_seconds), dtype=float)

    calibration_clocks = _refresh_pairs(
        int(reduced_config["calibration_clock_groups"]),
        int(reduced_config["calibration_clock_replications_per_group"]),
        rates,
        reduced_total_horizon,
        int(reduced_config["uniform_draws_per_book_clock"]),
        int(reduced_config["calibration_clock_seed"]),
        "CLK-CAL",
    )
    measured_rates = _measured_rates(calibration_clocks)

    reduced_paths = int(reduced_config["validation_operational_paths"])
    rho_u = float(reduced_config["operational_correlation"])
    operational_times, reduced_prices, measured_reduced_rho = _brownian_prices(
        reduced_paths,
        reduced_steps,
        step_seconds,
        rho_u,
        float(reduced_config["innovation_scale"]),
        int(reduced_config["operational_seed"]),
    )
    reduced_clocks = _refresh_pairs(
        reduced_paths,
        int(reduced_config["clock_replications_per_path"]),
        rates,
        reduced_total_horizon,
        int(reduced_config["uniform_draws_per_book_clock"]),
        int(reduced_config["validation_clock_seed"]),
        "CLK-REF",
    )
    reduced_components, reduced_overlap_components, reduced_maximum_index = (
        _clocked_component_groups(
            operational_times,
            reduced_prices,
            reduced_clocks,
            reduced_query_times,
            lag_steps,
        )
    )
    reduced_summary = pooled_correlation_summary(reduced_components)
    reduced_overlap_summary = pooled_correlation_summary(reduced_overlap_components)
    reduced_curve = reduced_summary.correlation / rho_u
    reduced_se = reduced_summary.jackknife_standard_error / abs(rho_u)
    reduced_overlap = reduced_overlap_summary.correlation
    reduced_metrics = _curve_metrics(reduced_curve, reduced_se, theory)
    reduced_overlap_rmse = float(
        np.sqrt(np.mean((reduced_overlap - theory) ** 2))
    )

    calibration_boundary, measured_calibration_rho = _boundary_ensemble(
        configuration,
        int(boundary_config["calibration_operational_paths"]),
        boundary_steps,
        int(boundary_config["calibration_operational_seed"]),
    )
    validation_boundary, measured_validation_rho = _boundary_ensemble(
        configuration,
        int(boundary_config["validation_operational_paths"]),
        boundary_steps,
        int(boundary_config["validation_operational_seed"]),
    )
    np.savez_compressed(
        BOUNDARY_PATH,
        operational_times_model=calibration_boundary.operational_times,
        operational_times_seconds=(
            calibration_boundary.operational_times
            * float(time["seconds_per_model_time_unit"])
        ),
        calibration_identity_prices=calibration_boundary.prices,
        validation_operational_prices=validation_boundary.prices,
    )
    identity_components = _identity_component_groups(
        calibration_boundary.prices, boundary_query_indices, lag_steps
    )
    identity_summary = pooled_correlation_summary(identity_components)
    boundary_clocks = _refresh_pairs(
        int(boundary_config["validation_operational_paths"]),
        int(boundary_config["clock_replications_per_validation_path"]),
        rates,
        boundary_total_horizon,
        int(boundary_config["uniform_draws_per_book_clock"]),
        int(boundary_config["validation_clock_seed"]),
        "CLK-LOB",
    )
    boundary_components, boundary_overlap_components, boundary_maximum_index = (
        _clocked_component_groups(
            calibration_boundary.operational_times
            * float(time["seconds_per_model_time_unit"]),
            validation_boundary.prices,
            boundary_clocks,
            boundary_query_times,
            lag_steps,
        )
    )
    boundary_summary = pooled_correlation_summary(boundary_components)
    boundary_overlap_summary = pooled_correlation_summary(boundary_overlap_components)
    identity_curve = identity_summary.correlation
    boundary_curve = boundary_summary.correlation / identity_curve
    boundary_se = np.sqrt(
        (boundary_summary.jackknife_standard_error / identity_curve) ** 2
        + (
            boundary_summary.correlation
            * identity_summary.jackknife_standard_error
            / identity_curve**2
        )
        ** 2
    )
    boundary_overlap = boundary_overlap_summary.correlation
    boundary_metrics = _curve_metrics(boundary_curve, boundary_se, theory)
    boundary_overlap_rmse = float(
        np.sqrt(np.mean((boundary_overlap - theory) ** 2))
    )

    reduced_recovered = bool(
        reduced_metrics[0] <= float(policy["absolute_curve_rmse_maximum"])
        and reduced_metrics[1] <= float(policy["standardized_curve_rmse_maximum"])
        and reduced_metrics[2] >= float(policy["minimum_pointwise_normal_95_coverage"])
        and reduced_metrics[3] <= float(policy["plateau_relative_shift_maximum"])
        and reduced_overlap_rmse <= float(policy["exact_overlap_curve_rmse_maximum"])
    )
    boundary_recovered = bool(
        boundary_metrics[0] <= float(policy["absolute_curve_rmse_maximum"])
        and boundary_metrics[1] <= float(policy["standardized_curve_rmse_maximum"])
        and boundary_metrics[2] >= float(policy["minimum_pointwise_normal_95_coverage"])
        and boundary_metrics[3] <= float(policy["plateau_relative_shift_maximum"])
        and boundary_overlap_rmse <= float(policy["exact_overlap_curve_rmse_maximum"])
    )
    rate_errors = np.abs(measured_rates - np.asarray(rates)) / np.asarray(rates)
    old_pooled_rmse = float(np.sqrt(np.mean((old_pooled - theory) ** 2)))
    boundary_numerically_valid = bool(
        calibration_boundary.completed_steps == boundary_steps
        and validation_boundary.completed_steps == boundary_steps
        and np.max(calibration_boundary.boundary_candidate_counts) == 1
        and np.max(validation_boundary.boundary_candidate_counts) == 1
        and np.min(calibration_boundary.boundary_edge_distances) > 8.0
        and np.min(validation_boundary.boundary_edge_distances) > 8.0
        and boundary_maximum_index < boundary_steps
    )

    curve_rows = []
    for position, lag in enumerate(lags_seconds):
        for tier, estimate, standard_error, overlap, identity in (
            ("reduced_reference", reduced_curve, reduced_se, reduced_overlap, np.full_like(theory, rho_u)),
            ("thick_boundary", boundary_curve, boundary_se, boundary_overlap, identity_curve),
        ):
            curve_rows.append(
                {
                    "tier": tier,
                    "target_id": "CNF-CLK-REF-01" if tier == "reduced_reference" else "CNF-CLK-LOB-01",
                    "lag_seconds": lag,
                    "exact_equal_rate_curve": theory[position],
                    "old_pooled_rate_envelope": old_pooled[position],
                    "normalized_simulation": estimate[position],
                    "jackknife_standard_error": standard_error[position],
                    "normal_95_lower": estimate[position] - 1.96 * standard_error[position],
                    "normal_95_upper": estimate[position] + 1.96 * standard_error[position],
                    "realized_exact_overlap": overlap[position],
                    "identity_reference_correlation": identity[position],
                    "equal_book_rate_per_second": displayed_rate,
                    "pooled_minimum_wait_rate_per_second": pooled_rate,
                    "subordination": "previous_refresh_then_previous_uniform_state",
                    "estimator": "ratio_of_pooled_cross_and_square_sums",
                    "software_version": VERSION,
                }
            )
    write_csv(CURVE_PATH, list(curve_rows[0]), curve_rows)

    reduced_label = "recovered" if reduced_recovered else "invalid_experiment"
    if boundary_recovered:
        boundary_label = "recovered"
    elif reduced_recovered and boundary_numerically_valid:
        boundary_label = "qualified_nonconformity"
    else:
        boundary_label = "invalid_experiment"
    summary_rows = [
        {
            "tier": "reduced_reference",
            "target_id": "CNF-CLK-REF-01",
            "result_label": reduced_label,
            "curve_rmse": reduced_metrics[0],
            "standardized_curve_rmse": reduced_metrics[1],
            "pointwise_normal_95_coverage": reduced_metrics[2],
            "plateau_relative_shift": reduced_metrics[3],
            "exact_overlap_rmse": reduced_overlap_rmse,
            "measured_operational_innovation_correlation": measured_reduced_rho,
            "minimum_boundary_edge_distance": "not_applicable",
            "maximum_boundary_candidate_count": "not_applicable",
            "software_version": VERSION,
        },
        {
            "tier": "thick_boundary",
            "target_id": "CNF-CLK-LOB-01",
            "result_label": boundary_label,
            "curve_rmse": boundary_metrics[0],
            "standardized_curve_rmse": boundary_metrics[1],
            "pointwise_normal_95_coverage": boundary_metrics[2],
            "plateau_relative_shift": boundary_metrics[3],
            "exact_overlap_rmse": boundary_overlap_rmse,
            "measured_operational_innovation_correlation": measured_validation_rho,
            "minimum_boundary_edge_distance": min(
                float(np.min(calibration_boundary.boundary_edge_distances)),
                float(np.min(validation_boundary.boundary_edge_distances)),
            ),
            "maximum_boundary_candidate_count": max(
                int(np.max(calibration_boundary.boundary_candidate_counts)),
                int(np.max(validation_boundary.boundary_candidate_counts)),
            ),
            "software_version": VERSION,
        },
    ]
    write_csv(SUMMARY_PATH, list(summary_rows[0]), summary_rows)

    checks = [
        _check("S7CLK-01", "uniform operational time resolution", step_seconds, "equals 0.5 seconds", np.isclose(step_seconds, 0.5)),
        _check("S7CLK-02", "equal book refresh-rate correction", rates, "both equal displayed rate 0.1 per second", rates == (displayed_rate, displayed_rate) == (0.1, 0.1)),
        _check("S7CLK-03", "pooled minimum-wait rate retained as diagnostic", pooled_rate, "equals sum of book rates 0.2 per second", np.isclose(pooled_rate, sum(rates))),
        _check("S7CLK-04", "calibration waiting-time rates", np.max(rate_errors), f"maximum relative error <= {policy['rate_relative_error_maximum']}", np.max(rate_errors) <= float(policy["rate_relative_error_maximum"])),
        _check("S7CLK-05", "reduced operational innovation correlation", measured_reduced_rho, "equals declared rho_u=0.8", np.isclose(measured_reduced_rho, rho_u, atol=1e-14)),
        _check("S7CLK-06", "reduced exact-overlap recovery", reduced_overlap_rmse, f"RMSE <= {policy['exact_overlap_curve_rmse_maximum']}", reduced_overlap_rmse <= float(policy["exact_overlap_curve_rmse_maximum"])),
        _check("S7CLK-07", "reduced clock-only absolute recovery", reduced_metrics[0], f"RMSE <= {policy['absolute_curve_rmse_maximum']}", reduced_metrics[0] <= float(policy["absolute_curve_rmse_maximum"])),
        _check("S7CLK-08", "reduced standardized recovery", reduced_metrics[1], f"standardized RMSE <= {policy['standardized_curve_rmse_maximum']}", reduced_metrics[1] <= float(policy["standardized_curve_rmse_maximum"])),
        _check("S7CLK-09", "reduced pointwise coverage", reduced_metrics[2], f"coverage >= {policy['minimum_pointwise_normal_95_coverage']}", reduced_metrics[2] >= float(policy["minimum_pointwise_normal_95_coverage"])),
        _check("S7CLK-10", "reduced plateau stability", reduced_metrics[3], f"relative shift <= {policy['plateau_relative_shift_maximum']}", reduced_metrics[3] <= float(policy["plateau_relative_shift_maximum"])),
        _check("S7CLK-11", "old pooled-rate envelope is separated", old_pooled_rmse, f"RMSE from exact curve >= {policy['rejected_pooled_curve_rmse_minimum']}", old_pooled_rmse >= float(policy["rejected_pooled_curve_rmse_minimum"])),
        _check("S7CLK-12", "reduced refresh support", reduced_maximum_index, f"strictly below terminal operational index {reduced_steps}", reduced_maximum_index < reduced_steps),
        _check("S7CLK-13", "thick-boundary numerical validity", boundary_numerically_valid, "complete paths, unique interior boundaries and no terminal extension", boundary_numerically_valid),
        _check("S7CLK-14", "thick-boundary input correlation", max(abs(measured_calibration_rho - 0.8), abs(measured_validation_rho - 0.8)), "maximum absolute error <= 1e-14", max(abs(measured_calibration_rho - 0.8), abs(measured_validation_rho - 0.8)) <= 1e-14),
        _check("S7CLK-15", "thick-boundary exact-overlap recovery", boundary_overlap_rmse, f"RMSE <= {policy['exact_overlap_curve_rmse_maximum']}", boundary_overlap_rmse <= float(policy["exact_overlap_curve_rmse_maximum"])),
        _check("S7CLK-16", "thick-boundary absolute recovery", boundary_metrics[0], f"RMSE <= {policy['absolute_curve_rmse_maximum']} or qualify full-model reduction", boundary_metrics[0] <= float(policy["absolute_curve_rmse_maximum"]), qualification_allowed=reduced_recovered and boundary_numerically_valid),
        _check("S7CLK-17", "thick-boundary standardized recovery", boundary_metrics[1], f"standardized RMSE <= {policy['standardized_curve_rmse_maximum']} or qualify full-model reduction", boundary_metrics[1] <= float(policy["standardized_curve_rmse_maximum"]), qualification_allowed=reduced_recovered and boundary_numerically_valid),
        _check("S7CLK-18", "thick-boundary pointwise coverage", boundary_metrics[2], f"coverage >= {policy['minimum_pointwise_normal_95_coverage']} or qualify full-model reduction", boundary_metrics[2] >= float(policy["minimum_pointwise_normal_95_coverage"]), qualification_allowed=reduced_recovered and boundary_numerically_valid),
        _check("S7CLK-19", "thick-boundary plateau stability", boundary_metrics[3], f"relative shift <= {policy['plateau_relative_shift_maximum']} or qualify full-model reduction", boundary_metrics[3] <= float(policy["plateau_relative_shift_maximum"]), qualification_allowed=reduced_recovered and boundary_numerically_valid),
        _check("S7CLK-20", "curve output contract", len(curve_rows), "exactly 40 rows", len(curve_rows) == 40),
        _check("S7CLK-21", "reduced-reference gate result", reduced_label, "recovered", reduced_label == "recovered"),
        _check("S7CLK-22", "permitted thick-boundary result label", boundary_label, "recovered or qualified_nonconformity", boundary_label in ("recovered", "qualified_nonconformity")),
    ]
    write_csv(CHECK_PATH, list(checks[0]), checks)
    _plot(
        lags_seconds,
        theory,
        old_pooled,
        reduced_curve,
        reduced_se,
        reduced_overlap,
        boundary_curve,
        boundary_se,
        boundary_overlap,
    )
    for row in checks:
        print(f"{row['check_id']}: {row['status']} - {row['check']}")
    failures = [row for row in checks if row["status"] == "Failed"]
    if failures:
        print(f"Clock-only conformity route failed: {len(failures)} required check(s).")
        return 1
    qualified = sum(row["status"] == "Qualified" for row in checks)
    print(
        f"Clock-only conformity route completed: {len(checks) - qualified} checks "
        f"verified, {qualified} qualified full-model checks, 0 failures."
    )
    print(f"Reduced reference: {reduced_label}; thick boundary: {boundary_label}.")
    print("Figure 19 generated as PDF and PNG with 40 machine-readable curve rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
