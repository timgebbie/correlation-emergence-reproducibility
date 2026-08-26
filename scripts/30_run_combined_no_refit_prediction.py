"""Run the v1.7.11 combined clock/corrected-coupling no-refit gate."""

from __future__ import annotations

import csv
import hashlib
import json
import math
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
from functions.integrity import accepted_input_errors
from functions.io_utils import write_csv
from functions.observation import (
    poisson_refresh_path_from_uniforms,
    pooled_correlation_summary,
    return_component_sums,
    subordinate_two_book_previous_refresh,
    symmetric_previous_refresh_expected_components,
)
from functions.operational import (
    OperationalSolverSpec,
    OperationalSource,
    TranslationModeCoupling,
    TwoBookInnovationPolicy,
    apply_spatial_boundary,
    coupling_covariance_build_up,
    operational_sibuya_kernel,
    operational_source_density,
    operational_translation_two_book_path,
    stationary_density,
    symmetric_linear_coupling_paths,
)


CONFIG_PATH = PROJECT_ROOT / "config" / "config-v1.7.11.json"
CHECK_PATH = PROJECT_ROOT / "diagnostics" / "combined-no-refit-checks-v1.7.csv"
CURVE_PATH = PROJECT_ROOT / "outputs" / "combined-no-refit-curves-v1.7.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "combined-no-refit-summary-v1.7.csv"
CLOCK_PATH = PROJECT_ROOT / "outputs" / "combined-no-refit-clock-rates-v1.7.csv"
ARCHIVE_PATH = PROJECT_ROOT / "outputs" / "combined-no-refit-paths-v1.7.npz"
FIGURE_STEM = PROJECT_ROOT / "figures" / "figure-22-combined-no-refit-prediction-v1"
VERSION = "1.7.11"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_configuration() -> dict[str, object]:
    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if configuration.get("schema_version") != VERSION:
        raise ValueError("combined no-refit configuration version mismatch")
    architecture = configuration["architecture"]
    if architecture["operational_dynamics"] != "uniform_fixed_grid_only":
        raise ValueError("v1.7.11 requires uniform operational dynamics")
    if architecture["combined_curve_refit"] != "forbidden":
        raise ValueError("v1.7.11 forbids a combined-curve refit")
    return configuration


def _accepted_hashes_valid(configuration: dict[str, object]) -> bool:
    return not accepted_input_errors(configuration["accepted_inputs"])


def _orthogonal_normal_inputs(paths: int, steps: int, seed: int) -> np.ndarray:
    values = np.random.default_rng(seed).standard_normal((paths * steps, 2))
    first = values[:, 0]
    second = values[:, 1]
    first -= np.mean(first)
    second -= np.mean(second)
    first *= np.sqrt(first.size / np.dot(first, first))
    second -= first * np.dot(first, second) / np.dot(first, first)
    second *= np.sqrt(second.size / np.dot(second, second))
    return np.stack((first, second), axis=1).reshape(paths, steps, 2)


def _standardized_vector(size: int, seed: int) -> np.ndarray:
    values = np.random.default_rng(seed).standard_normal(size)
    values -= np.mean(values)
    values *= np.sqrt(values.size / np.dot(values, values))
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
    uniforms = np.clip(
        uniforms, np.nextafter(0.0, 1.0), np.nextafter(1.0, 0.0)
    )
    result = []
    for group in range(groups):
        replications_result = []
        for replication in range(replications):
            replications_result.append(
                tuple(
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
            )
        result.append(tuple(replications_result))
    return tuple(result)


def _measured_rates(refresh_pairs) -> np.ndarray:
    counts = np.zeros(2, dtype=float)
    waits = np.zeros(2, dtype=float)
    for group in refresh_pairs:
        for replication in group:
            for book, path in enumerate(replication):
                counts[book] += path.waiting_intervals.size
                waits[book] += np.sum(path.waiting_intervals)
    return counts / waits


def _clocked_components(
    operational_times: np.ndarray,
    prices: np.ndarray,
    refresh_pairs,
    query_times: np.ndarray,
    lag_steps: np.ndarray,
    response_rate: float,
) -> tuple[np.ndarray, np.ndarray, int]:
    groups = prices.shape[0]
    if len(refresh_pairs) != groups:
        raise ValueError("refresh groups and operational paths must agree")
    observed = np.zeros((groups, lag_steps.size, 3), dtype=float)
    exact = np.zeros_like(observed)
    maximum_index = 0
    operational_step = float(operational_times[1] - operational_times[0])
    for group in range(groups):
        for paths in refresh_pairs[group]:
            sampled = subordinate_two_book_previous_refresh(
                operational_times,
                prices[group],
                paths,
                query_times,
            )
            observed[group] += return_component_sums(sampled.prices, lag_steps)
            exact[group] += symmetric_previous_refresh_expected_components(
                sampled.operational_indices,
                lag_steps,
                operational_step=operational_step,
                response_rate=response_rate,
            )
            maximum_index = max(
                maximum_index, int(np.max(sampled.operational_indices))
            )
    return observed, exact, maximum_index


def _ratio(values: np.ndarray) -> np.ndarray:
    denominator = np.sqrt(values[..., 1] * values[..., 2])
    if np.any(denominator <= 0.0):
        raise ValueError("component variation must be positive")
    return values[..., 0] / denominator


def _ratio_summary(
    numerators: np.ndarray, denominators: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    numerator = np.asarray(numerators, dtype=float)
    denominator = np.asarray(denominators, dtype=float)
    if numerator.ndim != 2 or denominator.shape != numerator.shape:
        raise ValueError("ratio inputs must share shape (groups, lags)")
    total_numerator = np.sum(numerator, axis=0)
    total_denominator = np.sum(denominator, axis=0)
    estimate = total_numerator / total_denominator
    leave_one_out = np.empty_like(numerator)
    for group in range(numerator.shape[0]):
        leave_one_out[group] = (
            total_numerator - numerator[group]
        ) / (total_denominator - denominator[group])
    centre = np.mean(leave_one_out, axis=0)
    standard_error = np.sqrt(
        (numerator.shape[0] - 1.0)
        / numerator.shape[0]
        * np.sum((leave_one_out - centre) ** 2, axis=0)
    )
    return estimate, standard_error


def _paired_ratio_residual_standard_error(
    observed_numerators: np.ndarray,
    observed_denominators: np.ndarray,
    reference_numerators: np.ndarray,
    reference_denominators: np.ndarray,
) -> np.ndarray:
    groups = observed_numerators.shape[0]
    totals = tuple(
        np.sum(values, axis=0)
        for values in (
            observed_numerators,
            observed_denominators,
            reference_numerators,
            reference_denominators,
        )
    )
    leave_one_out = np.empty_like(observed_numerators)
    for group in range(groups):
        leave_one_out[group] = (
            (totals[0] - observed_numerators[group])
            / (totals[1] - observed_denominators[group])
            - (totals[2] - reference_numerators[group])
            / (totals[3] - reference_denominators[group])
        )
    centre = np.mean(leave_one_out, axis=0)
    return np.sqrt(
        (groups - 1.0)
        / groups
        * np.sum((leave_one_out - centre) ** 2, axis=0)
    )


def _paired_correlation_residual_standard_error(
    observed: np.ndarray, reference: np.ndarray
) -> np.ndarray:
    groups = observed.shape[0]
    observed_total = np.sum(observed, axis=0)
    reference_total = np.sum(reference, axis=0)
    leave_one_out = np.empty((groups, observed.shape[1]), dtype=float)
    for group in range(groups):
        leave_one_out[group] = _ratio(observed_total - observed[group]) - _ratio(
            reference_total - reference[group]
        )
    centre = np.mean(leave_one_out, axis=0)
    return np.sqrt(
        (groups - 1.0)
        / groups
        * np.sum((leave_one_out - centre) ** 2, axis=0)
    )


def _metrics(
    estimate: np.ndarray, reference: np.ndarray, residual_standard_error: np.ndarray
) -> dict[str, float]:
    residual = np.asarray(estimate) - np.asarray(reference)
    error = np.asarray(residual_standard_error)
    if np.any(error <= 0.0) or not np.all(np.isfinite(error)):
        raise ValueError("residual standard errors must be finite and positive")
    first_band = float(np.mean(estimate[-10:-5]))
    second_band = float(np.mean(estimate[-5:]))
    return {
        "rmse": float(np.sqrt(np.mean(residual**2))),
        "standardized_rmse": float(np.sqrt(np.mean((residual / error) ** 2))),
        "coverage": float(np.mean(np.abs(residual) <= 1.96 * error)),
        "plateau_shift": abs(second_band - first_band) / abs(second_band),
        "maximum_absolute_residual": float(np.max(np.abs(residual))),
    }


def _plain_residual_metrics(estimate: np.ndarray, reference: np.ndarray) -> dict[str, float]:
    residual = np.asarray(estimate) - np.asarray(reference)
    return {
        "rmse": float(np.sqrt(np.mean(residual**2))),
        "maximum_absolute_residual": float(np.max(np.abs(residual))),
    }


def _operational_model(configuration: dict[str, object]):
    accepted = json.loads(
        (PROJECT_ROOT / "config" / "config-v1.7.7.json").read_text(encoding="utf-8")
    )
    model = accepted["model"]
    grid = np.linspace(
        float(model["grid_lower"]),
        float(model["grid_upper"]),
        int(model["primary_grid_points"]),
    )
    delta_x = float(grid[1] - grid[0])
    diffusion = tuple(float(value) for value in model["diffusion"])
    transport = float(model["transport_probability"])
    delta_u = transport * delta_x**2 / (2.0 * diffusion[0])
    if not np.isclose(
        delta_u,
        float(model["operational_step_model_units"]),
        rtol=1e-13,
        atol=1e-15,
    ):
        raise ValueError("accepted grid does not produce the frozen operational step")
    sources = tuple(
        OperationalSource(
            float(model["source_lambda"][book]),
            float(model["source_mu"][book]),
        )
        for book in range(2)
    )
    initial = np.stack(
        [
            apply_spatial_boundary(
                stationary_density(
                    grid,
                    np.asarray(operational_source_density(grid, 0.0, sources[book])),
                    diffusion=diffusion[book],
                    cancellation_rate=float(model["cancellation_rates"][book]),
                    boundary_condition="dirichlet_zero",
                )
            )
            for book in range(2)
        ]
    )
    kernels = tuple(
        operational_sibuya_kernel(
            float(model["operational_orders"][book]),
            int(model["kernel_terms"][book]),
        )
        for book in range(2)
    )
    specification = OperationalSolverSpec(
        delta_u=delta_u,
        transport_probability=transport,
        cancellation_rates=tuple(
            float(value) for value in model["cancellation_rates"]
        ),
        minimum_abs_boundary_slope=float(model["minimum_abs_boundary_slope"]),
    )
    rates = tuple(
        float(value)
        for value in configuration["frozen_components"][
            "ordered_coupling_rates_per_model_time_unit"
        ]
    )
    couplings = (
        (None, TranslationModeCoupling(rates[0])),
        (TranslationModeCoupling(rates[1]), None),
    )
    return grid, diffusion, sources, initial, kernels, specification, couplings


def _thick_boundary_ensemble(configuration: dict[str, object]) -> dict[str, object]:
    holdout = configuration["thick_boundary_holdout"]
    grid, diffusion, sources, initial, kernels, specification, couplings = (
        _operational_model(configuration)
    )
    paths = int(holdout["validation_paths"])
    steps = int(holdout["total_operational_steps"])
    base = _orthogonal_normal_inputs(paths, steps, int(holdout["operational_seed"]))
    accepted = json.loads(
        (PROJECT_ROOT / "config" / "config-v1.7.7.json").read_text(encoding="utf-8")
    )
    stochastic = accepted["stochastic_recovery"]
    policy = TwoBookInnovationPolicy(
        float(stochastic["innovation_sigma"][0]),
        float(stochastic["innovation_sigma"][1]),
        float(stochastic["microscopic_innovation_correlation"]),
    )
    price_paths = []
    minimum_edge = math.inf
    maximum_candidates = 0
    for path_index in range(paths):
        result = operational_translation_two_book_path(
            grid,
            initial,
            (0.0, 0.0),
            sources,
            couplings,
            kernels,
            base[path_index],
            policy,
            diffusion,
            specification,
        )
        price_paths.append(result.prices)
        minimum_edge = min(
            minimum_edge, float(np.min(result.boundary_edge_distances))
        )
        maximum_candidates = max(
            maximum_candidates, int(np.max(result.boundary_candidate_counts))
        )
        if (path_index + 1) % 8 == 0 or path_index + 1 == paths:
            print(f"  completed combined thick-boundary path {path_index + 1}/{paths}")
    return {
        "prices": np.stack(price_paths),
        "base": base,
        "delta_u": specification.delta_u,
        "completed_steps": steps,
        "minimum_edge": minimum_edge,
        "maximum_candidates": maximum_candidates,
    }


def _accepted_component_curves(lags_seconds: np.ndarray) -> dict[str, np.ndarray]:
    with (PROJECT_ROOT / "outputs" / "clock-only-conformity-curves-v1.7.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        clock_rows = [
            row for row in csv.DictReader(handle) if row["tier"] == "thick_boundary"
        ]
    with (
        PROJECT_ROOT / "outputs" / "corrected-coupling-recovery-curves-v1.7.csv"
    ).open(newline="", encoding="utf-8") as handle:
        coupling_rows = list(csv.DictReader(handle))
    clock_lags = np.asarray([float(row["lag_seconds"]) for row in clock_rows])
    coupling_lags = np.asarray([float(row["lag_seconds"]) for row in coupling_rows])
    if not (
        np.array_equal(clock_lags, lags_seconds)
        and np.array_equal(coupling_lags, lags_seconds)
    ):
        raise ValueError("accepted component curves must join on the exact v1.7.11 lags")
    clock = np.asarray([float(row["normalized_simulation"]) for row in clock_rows])
    clock_se = np.asarray([float(row["jackknife_standard_error"]) for row in clock_rows])
    coupling = np.asarray(
        [float(row["simulated_normalized_covariance"]) for row in coupling_rows]
    )
    coupling_se = np.asarray(
        [float(row["covariance_jackknife_standard_error"]) for row in coupling_rows]
    )
    product = clock * coupling
    product_se = np.sqrt((coupling * clock_se) ** 2 + (clock * coupling_se) ** 2)
    return {
        "clock": clock,
        "clock_se": clock_se,
        "coupling": coupling,
        "coupling_se": coupling_se,
        "product": product,
        "product_se": product_se,
    }


def _reduced_experiment(
    configuration: dict[str, object],
    lags_seconds: np.ndarray,
    lag_steps: np.ndarray,
) -> dict[str, object]:
    settings = configuration["exact_reduced_reference"]
    components = configuration["frozen_components"]
    paths = int(settings["validation_paths"])
    steps = int(settings["total_operational_steps"])
    replications = int(settings["clock_replications_per_path"])
    step = float(settings["operational_step_seconds"])
    response_rate = float(settings["response_rate_per_second"])
    base = _orthogonal_normal_inputs(paths, steps, int(settings["operational_seed"]))
    initial_spreads = _standardized_vector(
        paths, int(settings["initial_spread_seed"])
    )
    process = symmetric_linear_coupling_paths(
        base[:, :, 0],
        base[:, :, 1],
        initial_spreads,
        delta_time=step,
        response_rate=response_rate,
        innovation_scale=float(settings["innovation_scale"]),
    )
    warm_up = float(settings["warm_up_seconds"])
    horizon = float(settings["analysis_horizon_seconds"])
    query_times = warm_up + step * np.arange(int(round(horizon / step)) + 1)
    rates = tuple(
        float(value) for value in components["equal_book_refresh_rates_per_second"]
    )
    clocks = _refresh_pairs(
        paths,
        replications,
        rates,
        warm_up + horizon,
        int(settings["uniform_draws_per_book_clock"]),
        int(settings["clock_seed"]),
        "CMB-REF",
    )
    observed, exact, maximum_index = _clocked_components(
        process.times,
        process.prices,
        clocks,
        query_times,
        lag_steps,
        response_rate,
    )
    counts = query_times.size - lag_steps
    observed_denominators = np.broadcast_to(
        replications
        * counts
        * float(settings["pair_centre_variance_rate"])
        * lags_seconds,
        observed[:, :, 0].shape,
    ).copy()
    exact_denominators = np.broadcast_to(
        replications * counts * lags_seconds, exact[:, :, 0].shape
    ).copy()
    observed_covariance, observed_covariance_se = _ratio_summary(
        observed[:, :, 0], observed_denominators
    )
    exact_covariance, exact_covariance_se = _ratio_summary(
        exact[:, :, 0], exact_denominators
    )
    covariance_residual_se = _paired_ratio_residual_standard_error(
        observed[:, :, 0],
        observed_denominators,
        exact[:, :, 0],
        exact_denominators,
    )
    observed_correlation = pooled_correlation_summary(observed)
    exact_correlation = pooled_correlation_summary(exact)
    correlation_residual_se = _paired_correlation_residual_standard_error(
        observed, exact
    )
    return {
        "observed_components": observed,
        "exact_components": exact,
        "observed_covariance": observed_covariance,
        "observed_covariance_se": observed_covariance_se,
        "exact_covariance": exact_covariance,
        "exact_covariance_se": exact_covariance_se,
        "covariance_residual_se": covariance_residual_se,
        "observed_correlation": observed_correlation.correlation,
        "observed_correlation_se": observed_correlation.jackknife_standard_error,
        "exact_correlation": exact_correlation.correlation,
        "exact_correlation_se": exact_correlation.jackknife_standard_error,
        "correlation_residual_se": correlation_residual_se,
        "covariance_metrics": _metrics(
            observed_covariance, exact_covariance, covariance_residual_se
        ),
        "correlation_metrics": _metrics(
            observed_correlation.correlation,
            exact_correlation.correlation,
            correlation_residual_se,
        ),
        "measured_rates": _measured_rates(clocks),
        "maximum_index": maximum_index,
        "states": process.times.size,
        "input_correlation": float(
            np.corrcoef(base.reshape(-1, 2).T)[0, 1]
        ),
    }


def _thick_experiment(
    configuration: dict[str, object],
    lags_seconds: np.ndarray,
    lag_steps: np.ndarray,
) -> dict[str, object]:
    settings = configuration["thick_boundary_holdout"]
    frozen = configuration["frozen_components"]
    step_seconds = float(configuration["exact_reduced_reference"]["operational_step_seconds"])
    response_rate = float(frozen["total_coupling_rate_per_second"])
    replications = int(settings["clock_replications_per_path"])
    ensemble = _thick_boundary_ensemble(configuration)
    warm_up = int(settings["warm_up_steps"])
    prices = ensemble["prices"][:, warm_up:]
    operational_times = step_seconds * np.arange(prices.shape[1], dtype=float)
    query_times = operational_times.copy()
    horizon = float(settings["analysis_horizon_seconds"])
    if not np.isclose(query_times[-1], horizon):
        raise ValueError("thick-boundary holdout support does not match its horizon")
    rates = tuple(
        float(value) for value in frozen["equal_book_refresh_rates_per_second"]
    )
    clocks = _refresh_pairs(
        int(settings["validation_paths"]),
        replications,
        rates,
        horizon,
        int(settings["uniform_draws_per_book_clock"]),
        int(settings["clock_seed"]),
        "CMB-LOB",
    )
    observed, exact, maximum_index = _clocked_components(
        operational_times,
        prices,
        clocks,
        query_times,
        lag_steps,
        response_rate,
    )
    counts = query_times.size - lag_steps
    observed_denominators = np.broadcast_to(
        replications
        * counts
        * float(frozen["frozen_thick_boundary_covariance_scale"])
        * lags_seconds,
        observed[:, :, 0].shape,
    ).copy()
    exact_denominators = np.broadcast_to(
        replications * counts * lags_seconds, exact[:, :, 0].shape
    ).copy()
    observed_covariance, observed_covariance_se = _ratio_summary(
        observed[:, :, 0], observed_denominators
    )
    exact_covariance, exact_covariance_se = _ratio_summary(
        exact[:, :, 0], exact_denominators
    )
    covariance_residual_se = _paired_ratio_residual_standard_error(
        observed[:, :, 0],
        observed_denominators,
        exact[:, :, 0],
        exact_denominators,
    )
    observed_correlation = pooled_correlation_summary(observed)
    exact_correlation = pooled_correlation_summary(exact)
    correlation_residual_se = _paired_correlation_residual_standard_error(
        observed, exact
    )
    return {
        "prices": prices,
        "base": ensemble["base"],
        "observed_components": observed,
        "exact_components": exact,
        "observed_covariance": observed_covariance,
        "observed_covariance_se": observed_covariance_se,
        "exact_covariance": exact_covariance,
        "exact_covariance_se": exact_covariance_se,
        "covariance_residual_se": covariance_residual_se,
        "observed_correlation": observed_correlation.correlation,
        "observed_correlation_se": observed_correlation.jackknife_standard_error,
        "exact_correlation": exact_correlation.correlation,
        "exact_correlation_se": exact_correlation.jackknife_standard_error,
        "correlation_residual_se": correlation_residual_se,
        "covariance_metrics": _metrics(
            observed_covariance, exact_covariance, covariance_residual_se
        ),
        "correlation_metrics": _metrics(
            observed_correlation.correlation,
            exact_correlation.correlation,
            correlation_residual_se,
        ),
        "measured_rates": _measured_rates(clocks),
        "maximum_index": maximum_index,
        "states": prices.shape[1],
        "completed_steps": ensemble["completed_steps"],
        "minimum_edge": ensemble["minimum_edge"],
        "maximum_candidates": ensemble["maximum_candidates"],
        "input_correlation": float(
            np.corrcoef(ensemble["base"].reshape(-1, 2).T)[0, 1]
        ),
    }


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
    lags: np.ndarray,
    analytical_clock: np.ndarray,
    analytical_coupling: np.ndarray,
    analytical_product: np.ndarray,
    accepted: dict[str, np.ndarray],
    reduced: dict[str, object],
    thick: dict[str, object],
) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(11.4, 8.0), sharex="col")

    axis = axes[0, 0]
    axis.plot(lags, analytical_clock, color="#111111", lw=1.7, label=r"Theory clock $F(\lambda\Delta)$")
    axis.plot(lags, accepted["clock"], color="#111111", lw=1.1, ls=":", label="Accepted clock simulation")
    axis.plot(lags, analytical_coupling, color="#2166ac", lw=1.7, label=r"Theory coupling $F(\kappa\Delta)$")
    axis.plot(lags, accepted["coupling"], color="#2166ac", lw=1.1, ls=":", label="Accepted coupling simulation")
    axis.plot(lags, analytical_product, color="#b2182b", lw=2.0, label="Leading-order product")
    axis.plot(lags, accepted["product"], color="#d95f02", lw=1.3, ls="--", label="Accepted-component product")
    axis.set_ylabel("Normalized covariance response")
    axis.set_title("Frozen components and their two products")
    axis.legend(frameon=False, fontsize=7.0, loc="lower right")

    axis = axes[0, 1]
    axis.fill_between(
        lags,
        reduced["observed_covariance"] - 1.96 * reduced["observed_covariance_se"],
        reduced["observed_covariance"] + 1.96 * reduced["observed_covariance_se"],
        color="#92c5de",
        alpha=0.27,
        label="Reduced simulation 95% jackknife band",
    )
    axis.plot(lags, analytical_product, color="#111111", lw=1.7, ls="--", label="Leading-order product")
    axis.plot(lags, reduced["exact_covariance"], color="#666666", lw=1.8, label="Exact estimator-aware reference")
    axis.plot(lags, reduced["observed_covariance"], color="#2166ac", lw=1.6, label="Reduced simulation")
    axis.set_title("Reduced process: estimator versus separability")
    axis.legend(frameon=False, fontsize=7.2, loc="lower right")

    axis = axes[1, 0]
    axis.fill_between(
        lags,
        thick["observed_covariance"] - 1.96 * thick["observed_covariance_se"],
        thick["observed_covariance"] + 1.96 * thick["observed_covariance_se"],
        color="#f4a582",
        alpha=0.25,
        label="Thick-boundary holdout 95% band",
    )
    axis.plot(lags, analytical_product, color="#111111", lw=1.7, label="Leading-order product")
    axis.plot(lags, accepted["product"], color="#d95f02", lw=1.3, ls="--", label="Accepted-component product")
    axis.plot(lags, thick["exact_covariance"], color="#666666", lw=1.4, ls=":", label="Exact reduced same-clock reference")
    axis.plot(lags, thick["observed_covariance"], color="#b2182b", lw=1.7, label="Combined thick boundary")
    axis.set_xlabel(r"Calendar aggregation scale $\Delta t$ [s]")
    axis.set_ylabel("Normalized covariance response")
    axis.set_title("Combined holdout with no refit")
    axis.legend(frameon=False, fontsize=7.0, loc="lower right")

    axis = axes[1, 1]
    axis.axhline(0.0, color="#777777", lw=0.7)
    axis.plot(lags, reduced["exact_covariance"] - analytical_product, color="#111111", lw=1.4, label="Exact reduced - product")
    axis.plot(lags, thick["observed_covariance"] - thick["exact_covariance"], color="#5e3c99", lw=1.4, label="Boundary residual")
    axis.plot(lags, thick["observed_covariance"] - accepted["product"], color="#d95f02", lw=1.4, label="Nonseparability vs accepted components")
    axis.plot(lags, thick["observed_covariance"] - analytical_product, color="#b2182b", lw=1.7, label="Total product residual")
    axis.set_xlabel(r"Calendar aggregation scale $\Delta t$ [s]")
    axis.set_ylabel("Simulation/reference difference")
    axis.set_title("Registered residual decomposition")
    axis.legend(frameon=False, fontsize=7.0, loc="upper right")

    for axis in axes.ravel():
        axis.grid(alpha=0.18, linewidth=0.5)
        axis.set_xlim(float(lags[0]), float(lags[-1]))
    axes[0, 0].set_ylim(0.0, 1.08)
    axes[0, 1].set_ylim(0.0, 1.08)
    axes[1, 0].set_ylim(0.0, 1.08)
    figure.suptitle("Combined clock and corrected coupling: frozen-parameter holdout")
    figure.subplots_adjust(
        left=0.075, right=0.985, bottom=0.08, top=0.91, wspace=0.18, hspace=0.22
    )
    metadata = {
        "Creator": "correlation-emergence-v1.7.11",
        "CreationDate": None,
        "ModDate": None,
    }
    atomic_savefig(figure, FIGURE_STEM.with_suffix(".pdf"), metadata=metadata)
    atomic_savefig(figure, FIGURE_STEM.with_suffix(".png"), dpi=200)
    plt.close(figure)


def main() -> int:
    remove_orphaned_figure_staging_files()
    configuration = _load_configuration()
    policy = configuration["acceptance_policy"]
    frozen = configuration["frozen_components"]
    lags = np.asarray(configuration["registered_lags_seconds"], dtype=float)
    step = float(configuration["exact_reduced_reference"]["operational_step_seconds"])
    lag_steps = np.rint(lags / step).astype(int)
    clock_rate = float(frozen["equal_book_refresh_rates_per_second"][0])
    response_rate = float(frozen["total_coupling_rate_per_second"])
    analytical_clock = np.asarray(ordinary_build_up(clock_rate * lags), dtype=float)
    analytical_coupling = np.asarray(
        coupling_covariance_build_up(response_rate, lags), dtype=float
    )
    analytical_product = analytical_clock * analytical_coupling
    accepted = _accepted_component_curves(lags)

    print("Running exact reduced combined reference...")
    reduced = _reduced_experiment(configuration, lags, lag_steps)
    print("Running thick-boundary combined holdout...")
    thick = _thick_experiment(configuration, lags, lag_steps)

    product_metrics = _plain_residual_metrics(
        reduced["exact_covariance"], analytical_product
    )
    thick_total_metrics = _metrics(
        thick["observed_covariance"],
        analytical_product,
        thick["observed_covariance_se"],
    )
    thick_component_product_se = np.sqrt(
        thick["observed_covariance_se"] ** 2 + accepted["product_se"] ** 2
    )
    thick_component_metrics = _metrics(
        thick["observed_covariance"],
        accepted["product"],
        thick_component_product_se,
    )

    reduced_covariance = reduced["covariance_metrics"]
    reduced_correlation = reduced["correlation_metrics"]
    thick_covariance = thick["covariance_metrics"]
    thick_correlation = thick["correlation_metrics"]
    reduced_gate = bool(
        reduced_covariance["rmse"]
        <= float(policy["reduced_exact_covariance_rmse_maximum"])
        and reduced_covariance["standardized_rmse"]
        <= float(policy["standardized_rmse_maximum"])
        and reduced_covariance["coverage"]
        >= float(policy["minimum_pointwise_normal_95_coverage"])
        and reduced_correlation["rmse"]
        <= float(policy["reduced_exact_correlation_rmse_maximum"])
        and reduced_correlation["standardized_rmse"]
        <= float(policy["standardized_rmse_maximum"])
        and reduced_correlation["coverage"]
        >= float(policy["minimum_pointwise_normal_95_coverage"])
    )
    product_gate = bool(
        product_metrics["rmse"]
        <= float(policy["leading_order_product_rmse_maximum"])
    )
    boundary_gate = bool(
        thick_covariance["rmse"] <= float(policy["boundary_specific_rmse_maximum"])
        and thick_correlation["rmse"]
        <= float(policy["boundary_specific_rmse_maximum"])
    )
    component_product_gate = bool(
        thick_component_metrics["rmse"]
        <= float(policy["accepted_component_product_rmse_maximum"])
    )
    total_product_gate = bool(
        thick_total_metrics["rmse"]
        <= float(policy["leading_order_product_rmse_maximum"])
    )
    plateau_gate = bool(
        thick_total_metrics["plateau_shift"]
        <= float(policy["plateau_relative_shift_maximum"])
    )
    rate_target = np.asarray(frozen["equal_book_refresh_rates_per_second"], dtype=float)
    reduced_rate_errors = np.abs(reduced["measured_rates"] - rate_target) / rate_target
    thick_rate_errors = np.abs(thick["measured_rates"] - rate_target) / rate_target
    rate_gate = bool(
        np.max(reduced_rate_errors)
        <= float(policy["clock_rate_relative_error_maximum"])
        and np.max(thick_rate_errors)
        <= float(policy["clock_rate_relative_error_maximum"])
    )
    numerical_gate = bool(
        thick["completed_steps"]
        == int(configuration["thick_boundary_holdout"]["total_operational_steps"])
        and thick["maximum_candidates"] == 1
        and thick["minimum_edge"] > 8.0
        and thick["maximum_index"] < thick["states"] - 1
        and reduced["maximum_index"] < reduced["states"] - 1
    )
    if not reduced_gate or not rate_gate or not numerical_gate:
        result_label = "invalid_experiment"
    elif all(
        (product_gate, boundary_gate, component_product_gate, total_product_gate, plateau_gate)
    ):
        result_label = "recovered"
    else:
        result_label = "qualified_nonconformity"

    curve_rows = []
    for index, lag in enumerate(lags):
        curve_rows.append(
            {
                "target_id": "CNF-CMB-LOB-01",
                "lag_seconds": lag,
                "analytical_clock_factor": analytical_clock[index],
                "accepted_clock_thick_boundary": accepted["clock"][index],
                "analytical_coupling_factor": analytical_coupling[index],
                "accepted_corrected_coupling": accepted["coupling"][index],
                "analytical_leading_order_product": analytical_product[index],
                "accepted_component_product": accepted["product"][index],
                "accepted_component_product_standard_error": accepted["product_se"][index],
                "reduced_exact_conditional_covariance": reduced["exact_covariance"][index],
                "reduced_simulated_covariance": reduced["observed_covariance"][index],
                "reduced_covariance_standard_error": reduced["observed_covariance_se"][index],
                "reduced_covariance_residual_standard_error": reduced["covariance_residual_se"][index],
                "reduced_exact_conditional_correlation": reduced["exact_correlation"][index],
                "reduced_simulated_correlation": reduced["observed_correlation"][index],
                "reduced_correlation_residual_standard_error": reduced["correlation_residual_se"][index],
                "thick_exact_reduced_same_clock_covariance": thick["exact_covariance"][index],
                "thick_simulated_combined_covariance": thick["observed_covariance"][index],
                "thick_covariance_standard_error": thick["observed_covariance_se"][index],
                "thick_covariance_residual_standard_error": thick["covariance_residual_se"][index],
                "thick_exact_reduced_same_clock_correlation": thick["exact_correlation"][index],
                "thick_simulated_combined_correlation": thick["observed_correlation"][index],
                "thick_correlation_residual_standard_error": thick["correlation_residual_se"][index],
                "exact_reduced_minus_product": reduced["exact_covariance"][index] - analytical_product[index],
                "thick_minus_exact_reduced": thick["observed_covariance"][index] - thick["exact_covariance"][index],
                "thick_minus_accepted_component_product": thick["observed_covariance"][index] - accepted["product"][index],
                "thick_minus_analytical_product": thick["observed_covariance"][index] - analytical_product[index],
                "equal_book_clock_rate_per_second": clock_rate,
                "coupling_rate_per_second": response_rate,
                "frozen_covariance_scale": frozen["frozen_thick_boundary_covariance_scale"],
                "subordination": "previous_refresh_then_previous_uniform_state",
                "fit_policy": "no_component_or_combined_refit",
                "software_version": VERSION,
            }
        )
    write_csv(CURVE_PATH, list(curve_rows[0]), curve_rows)

    clock_rows = []
    for tier, rates, errors in (
        ("reduced_reference", reduced["measured_rates"], reduced_rate_errors),
        ("thick_boundary_holdout", thick["measured_rates"], thick_rate_errors),
    ):
        for book in range(2):
            clock_rows.append(
                {
                    "tier": tier,
                    "book": book + 1,
                    "target_rate_per_second": rate_target[book],
                    "measured_rate_per_second": rates[book],
                    "relative_error": errors[book],
                    "software_version": VERSION,
                }
            )
    write_csv(CLOCK_PATH, list(clock_rows[0]), clock_rows)

    summary_rows = [
        {
            "tier": "reduced_estimator_reference",
            "target_id": "CNF-CMB-REF-01",
            "result_label": "recovered" if reduced_gate else "invalid_experiment",
            "covariance_rmse": reduced_covariance["rmse"],
            "covariance_standardized_rmse": reduced_covariance["standardized_rmse"],
            "covariance_coverage": reduced_covariance["coverage"],
            "correlation_rmse": reduced_correlation["rmse"],
            "correlation_standardized_rmse": reduced_correlation["standardized_rmse"],
            "correlation_coverage": reduced_correlation["coverage"],
            "product_rmse": "not_applicable",
            "accepted_component_product_rmse": "not_applicable",
            "plateau_relative_shift": reduced_covariance["plateau_shift"],
            "interpretation": "exact_conditional_estimator_benchmark",
            "software_version": VERSION,
        },
        {
            "tier": "leading_order_product",
            "target_id": "CNF-CMB-REF-01",
            "result_label": "recovered" if product_gate else "qualified_nonconformity",
            "covariance_rmse": "not_applicable",
            "covariance_standardized_rmse": "not_applicable",
            "covariance_coverage": "not_applicable",
            "correlation_rmse": "not_applicable",
            "correlation_standardized_rmse": "not_applicable",
            "correlation_coverage": "not_applicable",
            "product_rmse": product_metrics["rmse"],
            "accepted_component_product_rmse": "not_applicable",
            "plateau_relative_shift": "not_applicable",
            "interpretation": "intrinsic_estimator_level_nonseparability",
            "software_version": VERSION,
        },
        {
            "tier": "thick_boundary_combined",
            "target_id": "CNF-CMB-LOB-01",
            "result_label": result_label,
            "covariance_rmse": thick_covariance["rmse"],
            "covariance_standardized_rmse": thick_covariance["standardized_rmse"],
            "covariance_coverage": thick_covariance["coverage"],
            "correlation_rmse": thick_correlation["rmse"],
            "correlation_standardized_rmse": thick_correlation["standardized_rmse"],
            "correlation_coverage": thick_correlation["coverage"],
            "product_rmse": thick_total_metrics["rmse"],
            "accepted_component_product_rmse": thick_component_metrics["rmse"],
            "plateau_relative_shift": thick_total_metrics["plateau_shift"],
            "interpretation": "boundary_specific_and_total_nonseparability_without_refit",
            "software_version": VERSION,
        },
    ]
    write_csv(SUMMARY_PATH, list(summary_rows[0]), summary_rows)

    np.savez_compressed(
        ARCHIVE_PATH,
        lags_seconds=lags,
        lag_steps=lag_steps,
        thick_validation_prices=thick["prices"],
        reduced_observed_components=reduced["observed_components"],
        reduced_exact_components=reduced["exact_components"],
        thick_observed_components=thick["observed_components"],
        thick_exact_components=thick["exact_components"],
        reduced_measured_clock_rates=reduced["measured_rates"],
        thick_measured_clock_rates=thick["measured_rates"],
        frozen_covariance_scale=np.asarray(frozen["frozen_thick_boundary_covariance_scale"]),
    )

    _plot(
        lags,
        analytical_clock,
        analytical_coupling,
        analytical_product,
        accepted,
        reduced,
        thick,
    )

    checks = [
        _check("S7CM-01", "accepted v1.7.7 input hashes", _accepted_hashes_valid(configuration), "all accepted hashes exact", _accepted_hashes_valid(configuration)),
        _check("S7CM-02", "accepted parent", configuration["accepted_parent"], "exactly v1.7.7", configuration["accepted_parent"] == "v1.7.7"),
        _check("S7CM-03", "uniform operational dynamics", configuration["architecture"]["operational_dynamics"], "uniform_fixed_grid_only", configuration["architecture"]["operational_dynamics"] == "uniform_fixed_grid_only"),
        _check("S7CM-04", "explicit post-dynamics clock", configuration["architecture"]["calendar_observation"], "independent previous refresh after operational completion", configuration["architecture"]["calendar_observation"] == "independent_equal_rate_previous_refresh_after_operational_completion"),
        _check("S7CM-05", "nonuniform update and interpolation excluded", (configuration["architecture"]["legacy_nonuniform_state_update"], configuration["architecture"]["calendar_interpolation"]), "both forbidden", configuration["architecture"]["legacy_nonuniform_state_update"] == "forbidden" and configuration["architecture"]["calendar_interpolation"] == "forbidden"),
        _check("S7CM-06", "component and combined refit excluded", (configuration["architecture"]["component_parameter_refit"], configuration["architecture"]["combined_curve_refit"]), "both forbidden", configuration["architecture"]["component_parameter_refit"] == "forbidden" and configuration["architecture"]["combined_curve_refit"] == "forbidden"),
        _check("S7CM-07", "exact reduced reference owns no clock or dynamics", configuration["exact_reduced_reference"]["exact_reference"], "conditional moments given selected indices", configuration["exact_reduced_reference"]["exact_reference"] == "conditional_gaussian_moments_given_selected_previous_refresh_operational_indices"),
        _check("S7CM-08", "reduced external input orthogonality", reduced["input_correlation"], "absolute correlation <= 1e-14", abs(reduced["input_correlation"]) <= 1e-14),
        _check("S7CM-09", "thick external input orthogonality", thick["input_correlation"], "absolute correlation <= 1e-14", abs(thick["input_correlation"]) <= 1e-14),
        _check("S7CM-10", "reduced realised clock rates", np.max(reduced_rate_errors), f"maximum relative error <= {policy['clock_rate_relative_error_maximum']}", np.max(reduced_rate_errors) <= float(policy["clock_rate_relative_error_maximum"])),
        _check("S7CM-11", "thick realised clock rates", np.max(thick_rate_errors), f"maximum relative error <= {policy['clock_rate_relative_error_maximum']}", np.max(thick_rate_errors) <= float(policy["clock_rate_relative_error_maximum"])),
        _check("S7CM-12", "reduced terminal state unused", reduced["maximum_index"], f"strictly below {reduced['states'] - 1}", reduced["maximum_index"] < reduced["states"] - 1),
        _check("S7CM-13", "reduced covariance exact-reference RMSE", reduced_covariance["rmse"], f"RMSE <= {policy['reduced_exact_covariance_rmse_maximum']}", reduced_covariance["rmse"] <= float(policy["reduced_exact_covariance_rmse_maximum"])),
        _check("S7CM-14", "reduced covariance standardized RMSE", reduced_covariance["standardized_rmse"], f"standardized RMSE <= {policy['standardized_rmse_maximum']}", reduced_covariance["standardized_rmse"] <= float(policy["standardized_rmse_maximum"])),
        _check("S7CM-15", "reduced covariance coverage", reduced_covariance["coverage"], f"coverage >= {policy['minimum_pointwise_normal_95_coverage']}", reduced_covariance["coverage"] >= float(policy["minimum_pointwise_normal_95_coverage"])),
        _check("S7CM-16", "reduced correlation exact-reference RMSE", reduced_correlation["rmse"], f"RMSE <= {policy['reduced_exact_correlation_rmse_maximum']}", reduced_correlation["rmse"] <= float(policy["reduced_exact_correlation_rmse_maximum"])),
        _check("S7CM-17", "reduced correlation standardized RMSE", reduced_correlation["standardized_rmse"], f"standardized RMSE <= {policy['standardized_rmse_maximum']}", reduced_correlation["standardized_rmse"] <= float(policy["standardized_rmse_maximum"])),
        _check("S7CM-18", "reduced correlation coverage", reduced_correlation["coverage"], f"coverage >= {policy['minimum_pointwise_normal_95_coverage']}", reduced_correlation["coverage"] >= float(policy["minimum_pointwise_normal_95_coverage"])),
        _check("S7CM-19", "reduced estimator gate", reduced_gate, "recovered before product interpretation", reduced_gate),
        _check("S7CM-20", "leading-order product approximation", product_metrics["rmse"], f"RMSE <= {policy['leading_order_product_rmse_maximum']} or qualified", product_gate, qualification_allowed=True),
        _check("S7CM-21", "leading-order product result label", "recovered" if product_gate else "qualified_nonconformity", "permitted scientific result", True),
        _check("S7CM-22", "thick completed operational paths", thick["completed_steps"], f"exactly {configuration['thick_boundary_holdout']['total_operational_steps']}", thick["completed_steps"] == int(configuration["thick_boundary_holdout"]["total_operational_steps"])),
        _check("S7CM-23", "thick unique boundaries", thick["maximum_candidates"], "exactly one candidate", thick["maximum_candidates"] == 1),
        _check("S7CM-24", "thick interior boundaries", thick["minimum_edge"], "minimum edge distance > 8", thick["minimum_edge"] > 8.0),
        _check("S7CM-25", "thick terminal state unused", thick["maximum_index"], f"strictly below {thick['states'] - 1}", thick["maximum_index"] < thick["states"] - 1),
        _check("S7CM-26", "accepted covariance scale retained", frozen["frozen_thick_boundary_covariance_scale"], "exact v1.7.7 frozen scale", float(frozen["frozen_thick_boundary_covariance_scale"]) == 1.0568450226140758e-06),
        _check("S7CM-27", "boundary-specific covariance residual", thick_covariance["rmse"], f"RMSE <= {policy['boundary_specific_rmse_maximum']} or qualified", thick_covariance["rmse"] <= float(policy["boundary_specific_rmse_maximum"]), qualification_allowed=True),
        _check("S7CM-28", "boundary-specific covariance standardized RMSE", thick_covariance["standardized_rmse"], f"standardized RMSE <= {policy['standardized_rmse_maximum']} or qualified", thick_covariance["standardized_rmse"] <= float(policy["standardized_rmse_maximum"]), qualification_allowed=True),
        _check("S7CM-29", "boundary-specific covariance coverage", thick_covariance["coverage"], f"coverage >= {policy['minimum_pointwise_normal_95_coverage']} or qualified", thick_covariance["coverage"] >= float(policy["minimum_pointwise_normal_95_coverage"]), qualification_allowed=True),
        _check("S7CM-30", "boundary-specific correlation residual", thick_correlation["rmse"], f"RMSE <= {policy['boundary_specific_rmse_maximum']} or qualified", thick_correlation["rmse"] <= float(policy["boundary_specific_rmse_maximum"]), qualification_allowed=True),
        _check("S7CM-31", "total analytical-product residual", thick_total_metrics["rmse"], f"RMSE <= {policy['leading_order_product_rmse_maximum']} or qualified", total_product_gate, qualification_allowed=True),
        _check("S7CM-32", "total product standardized RMSE", thick_total_metrics["standardized_rmse"], f"standardized RMSE <= {policy['standardized_rmse_maximum']} or qualified", thick_total_metrics["standardized_rmse"] <= float(policy["standardized_rmse_maximum"]), qualification_allowed=True),
        _check("S7CM-33", "total product coverage", thick_total_metrics["coverage"], f"coverage >= {policy['minimum_pointwise_normal_95_coverage']} or qualified", thick_total_metrics["coverage"] >= float(policy["minimum_pointwise_normal_95_coverage"]), qualification_allowed=True),
        _check("S7CM-34", "accepted-component-product residual", thick_component_metrics["rmse"], f"RMSE <= {policy['accepted_component_product_rmse_maximum']} or qualified", component_product_gate, qualification_allowed=True),
        _check("S7CM-35", "combined plateau stability", thick_total_metrics["plateau_shift"], f"relative shift <= {policy['plateau_relative_shift_maximum']} or qualified", plateau_gate, qualification_allowed=True),
        _check("S7CM-36", "source-v1 paper freeze", _sha256(PROJECT_ROOT / "source/source-v1/CATG-RD2Epps-v3-arXiv.tex"), "accepted source hash exact", _sha256(PROJECT_ROOT / "source/source-v1/CATG-RD2Epps-v3-arXiv.tex") == "48eea98a6fb084d6ecc397bede4c107a44cae947e16271d66a7041e2997afb5a"),
        _check("S7CM-37", "Figure 22 output pair", all(FIGURE_STEM.with_suffix(suffix).stat().st_size > 1000 for suffix in (".pdf", ".png")), "nonempty PDF and PNG", all(FIGURE_STEM.with_suffix(suffix).stat().st_size > 1000 for suffix in (".pdf", ".png"))),
        _check("S7CM-38", "Stage 7 remains open for closure", configuration["stage_boundary"]["next_stage_on_acceptance"], "v1.7.12 stability and integrity closure", configuration["stage_boundary"]["next_stage_on_acceptance"] == "v1.7.12_stage_7_stability_integrity_and_closure"),
    ]
    write_csv(CHECK_PATH, list(checks[0]), checks)
    failures = [row for row in checks if row["status"] == "Failed"]
    for row in checks:
        print(f"{row['check_id']}: {row['status']} - {row['check']}")
    if failures:
        print(f"Combined no-refit route failed: {len(failures)} failed checks.")
        return 1
    qualified = sum(row["status"] == "Qualified" for row in checks)
    print(
        "Combined no-refit prediction completed: "
        f"{len(checks) - qualified} checks verified, {qualified} qualified, "
        f"0 failures; result {result_label}."
    )
    print(
        "Figure 22 generated with frozen component parameters; Stage 7 remains "
        "open for the v1.7.12 stability and integrity closure."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
