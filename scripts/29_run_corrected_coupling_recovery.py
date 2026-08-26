"""Run the v1.7.7 corrected coupling deterministic and stochastic recovery."""

from __future__ import annotations

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

from functions.figure_io import atomic_savefig, remove_orphaned_figure_staging_files
from functions.integrity import accepted_input_errors, snapshot_errors, snapshot_hashes
from functions.io_utils import write_csv
from functions.observation import pooled_correlation_summary, return_component_sums
from functions.operational import (
    OperationalSolverSpec,
    OperationalSource,
    TranslationModeCoupling,
    TwoBookInnovationPolicy,
    apply_spatial_boundary,
    coupling_covariance_build_up,
    current_front_translation_mode,
    exponential_relaxation_rate,
    extract_reaction_boundary,
    linearized_translation_mode,
    local_drift_relaxation_rate,
    operational_sibuya_kernel,
    operational_source_density,
    operational_translation_two_book_path,
    operational_translation_two_book_step,
    stationary_density,
    symmetric_closed_sde_correlation,
    translation_mode_coupling_density,
)


VERSION = "1.7.7"
CONFIG_PATH = PROJECT_ROOT / "config" / "config-v1.7.7.json"
CHECK_PATH = PROJECT_ROOT / "diagnostics" / "corrected-coupling-recovery-checks-v1.7.csv"
CURVE_PATH = PROJECT_ROOT / "outputs" / "corrected-coupling-recovery-curves-v1.7.csv"
RATE_PATH = PROJECT_ROOT / "outputs" / "corrected-coupling-rate-summary-v1.7.csv"
RESPONSE_PATH = PROJECT_ROOT / "outputs" / "corrected-coupling-response-v1.7.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "corrected-coupling-recovery-summary-v1.7.csv"
PATH_ARCHIVE = PROJECT_ROOT / "outputs" / "corrected-coupling-validation-paths-v1.7.npz"
FIGURE_STEM = PROJECT_ROOT / "figures" / "figure-08-corrected-translation-mode-coupling-v2"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_configuration() -> dict[str, object]:
    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if configuration.get("schema_version") != VERSION:
        raise ValueError("corrected coupling configuration version mismatch")
    architecture = configuration["architecture"]
    if architecture["operational_dynamics"] != "uniform_fixed_grid_only":
        raise ValueError("v1.7.7 requires uniform operational dynamics")
    if architecture["calendar_observation"] != "identity_clock_only":
        raise ValueError("v1.7.7 requires the identity clock")
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


def _model(configuration: dict[str, object], points: int):
    model = configuration["model"]
    grid = np.linspace(
        float(model["grid_lower"]), float(model["grid_upper"]), points
    )
    delta_x = float(grid[1] - grid[0])
    diffusion = tuple(float(value) for value in model["diffusion"])
    transport = float(model["transport_probability"])
    delta_u = transport * delta_x**2 / (2.0 * diffusion[0])
    sources = tuple(
        OperationalSource(float(model["source_lambda"][book]), float(model["source_mu"][book]))
        for book in range(2)
    )
    stationary = np.stack(
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
        delta_u,
        transport,
        tuple(float(value) for value in model["cancellation_rates"]),
        minimum_abs_boundary_slope=float(model["minimum_abs_boundary_slope"]),
    )
    return grid, diffusion, sources, stationary, kernels, specification


def _coupling_matrix(configuration: dict[str, object]):
    rates = configuration["coupling"]["ordered_rates_per_model_time_unit"]
    first = TranslationModeCoupling(float(rates[0]))
    second = TranslationModeCoupling(float(rates[1]))
    return ((None, first), (second, None))


def _perturbed_initial_state(
    grid: np.ndarray,
    stationary: np.ndarray,
    displacement: float,
    minimum_slope: float,
) -> tuple[np.ndarray, np.ndarray]:
    densities = np.stack(
        (
            linearized_translation_mode(grid, stationary[0], displacement),
            linearized_translation_mode(grid, stationary[1], -displacement),
        )
    )
    prices = np.empty(2, dtype=float)
    for book, expected in enumerate((displacement, -displacement)):
        prices[book] = extract_reaction_boundary(
            grid,
            densities[book],
            selection="nearest_previous",
            previous_price=expected,
            minimum_abs_slope=minimum_slope,
        ).price
    return densities, prices


def _single_deterministic_response(
    configuration: dict[str, object],
    points: int,
    displacement: float,
) -> dict[str, object]:
    grid, diffusion, sources, stationary, kernels, specification = _model(
        configuration, points
    )
    deterministic = configuration["deterministic_recovery"]
    densities, prices = _perturbed_initial_state(
        grid,
        stationary,
        displacement,
        float(configuration["model"]["minimum_abs_boundary_slope"]),
    )
    response_steps = int(
        round(
            float(deterministic["response_horizon_model_units"])
            / specification.delta_u
        )
    )
    fit_steps = int(
        round(
            float(deterministic["fit_horizon_model_units"])
            / specification.delta_u
        )
    )
    zero_inputs = np.zeros((response_steps, 2), dtype=float)
    policy = TwoBookInnovationPolicy(0.0, 0.0, 0.0)
    common = {
        "price_grid": grid,
        "initial_densities": densities,
        "initial_prices": prices,
        "sources": sources,
        "raw_kernels": kernels,
        "base_standard_normals": zero_inputs,
        "innovation_policy": policy,
        "diffusion": diffusion,
        "solver_spec": specification,
    }
    control = operational_translation_two_book_path(
        **common, couplings=((None, None), (None, None))
    )
    coupled = operational_translation_two_book_path(
        **common, couplings=_coupling_matrix(configuration)
    )
    control_spread = (control.prices[:, 0] - control.prices[:, 1])[None, :]
    coupled_spread = (coupled.prices[:, 0] - coupled.prices[:, 1])[None, :]
    exponential = exponential_relaxation_rate(
        coupled.operational_times,
        coupled_spread,
        control_spread,
        maximum_time=float(deterministic["fit_horizon_model_units"]),
    )
    local = local_drift_relaxation_rate(
        coupled_spread,
        control_spread,
        delta_time=specification.delta_u,
        fit_steps=fit_steps,
    )

    matrix = _coupling_matrix(configuration)
    projection_residual = 0.0
    for receiving, other in ((0, 1), (1, 0)):
        coupling = matrix[receiving][other]
        mode = current_front_translation_mode(grid, densities[receiving])
        spread = prices[receiving] - prices[other]
        observed = translation_mode_coupling_density(
            grid,
            prices[receiving],
            prices[other],
            densities[receiving],
            coupling,
        )
        expected = -coupling.kappa_jk * spread * mode
        scale = max(float(np.linalg.norm(expected)), np.finfo(float).tiny)
        projection_residual = max(
            projection_residual,
            float(np.linalg.norm(observed - expected) / scale),
        )

    target = float(configuration["coupling"]["target_total_rate_per_model_time_unit"])
    induced_first_change = float(
        (coupled_spread[0, 1] - coupled_spread[0, 0])
        - (control_spread[0, 1] - control_spread[0, 0])
    )
    return {
        "grid_points": points,
        "delta_u": specification.delta_u,
        "displacement": displacement,
        "initial_spread": float(coupled_spread[0, 0]),
        "control_spread": control_spread[0],
        "coupled_spread": coupled_spread[0],
        "times": coupled.operational_times,
        "exponential_rate": exponential.response_rate,
        "exponential_rmse": exponential.root_mean_square_residual,
        "local_rate": local.response_rate,
        "local_rmse": local.root_mean_square_residual,
        "exponential_relative_error": abs(exponential.response_rate - target) / target,
        "local_relative_error": abs(local.response_rate - target) / target,
        "rate_relative_difference": abs(exponential.response_rate - local.response_rate)
        / target,
        "projection_residual": projection_residual,
        "maximum_absolute_pair_center_drift": float(
            np.max(np.abs(coupled.pair_centres - coupled.pair_centres[0]))
        ),
        "minimum_boundary_edge_distance": float(
            np.min(coupled.boundary_edge_distances)
        ),
        "maximum_boundary_candidates": int(
            np.max(coupled.boundary_candidate_counts)
        ),
        "sign_preserved": bool(exponential.sign_preserved and local.sign_preserved),
        "receiving_sign_correct": bool(
            induced_first_change * coupled_spread[0, 0] < 0.0
        ),
    }


def _deterministic_recovery(configuration: dict[str, object]) -> dict[str, object]:
    deterministic = configuration["deterministic_recovery"]
    primary_points = int(configuration["model"]["primary_grid_points"])
    primary = []
    for sign in deterministic["perturbation_signs"]:
        for displacement in deterministic["book_displacements"]:
            primary.append(
                _single_deterministic_response(
                    configuration,
                    primary_points,
                    float(sign) * float(displacement),
                )
            )
    grid_rows = [
        _single_deterministic_response(
            configuration,
            int(points),
            float(deterministic["grid_probe_displacement"]),
        )
        for points in configuration["model"]["grid_convergence_points"]
    ]

    grid, _, sources, stationary, kernels, specification = _model(
        configuration, primary_points
    )
    matrix = _coupling_matrix(configuration)
    zero_step = operational_translation_two_book_step(
        grid,
        stationary[:, :, None],
        (0.0, 0.0),
        sources,
        matrix,
        kernels,
        (0.0, 0.0),
        specification,
    )
    zero_stationary_error = float(
        np.max(np.abs(zero_step.densities - stationary))
    )
    zero_coupling_maximum = float(np.max(np.abs(zero_step.total_coupling_fields)))

    rate_rows = []
    response_rows = []
    for index, result in enumerate(primary):
        rate_rows.append(
            {
                "record_type": "primary_signed_perturbation",
                "record_index": index,
                "grid_points": result["grid_points"],
                "delta_u": result["delta_u"],
                "book_one_displacement": result["displacement"],
                "initial_spread": result["initial_spread"],
                "exponential_rate_per_model_time_unit": result["exponential_rate"],
                "local_drift_rate_per_model_time_unit": result["local_rate"],
                "exponential_rate_relative_error": result["exponential_relative_error"],
                "local_rate_relative_error": result["local_relative_error"],
                "rate_measurement_relative_difference": result["rate_relative_difference"],
                "exponential_log_ratio_rmse": result["exponential_rmse"],
                "local_drift_rmse": result["local_rmse"],
                "projection_relative_residual": result["projection_residual"],
                "maximum_absolute_pair_center_drift": result["maximum_absolute_pair_center_drift"],
                "minimum_boundary_edge_distance": result["minimum_boundary_edge_distance"],
                "maximum_boundary_candidates": result["maximum_boundary_candidates"],
                "sign_preserved": result["sign_preserved"],
                "receiving_sign_correct": result["receiving_sign_correct"],
                "software_version": VERSION,
            }
        )
        for step, time in enumerate(result["times"]):
            response_rows.append(
                {
                    "record_index": index,
                    "book_one_displacement": result["displacement"],
                    "operational_step": step,
                    "operational_time_model_units": time,
                    "time_seconds": time
                    * float(configuration["model"]["seconds_per_model_time_unit"]),
                    "control_spread": result["control_spread"][step],
                    "coupled_spread": result["coupled_spread"][step],
                    "paired_spread_ratio": result["coupled_spread"][step]
                    / result["control_spread"][step],
                    "software_version": VERSION,
                }
            )
    for index, result in enumerate(grid_rows):
        rate_rows.append(
            {
                "record_type": "grid_convergence",
                "record_index": index,
                "grid_points": result["grid_points"],
                "delta_u": result["delta_u"],
                "book_one_displacement": result["displacement"],
                "initial_spread": result["initial_spread"],
                "exponential_rate_per_model_time_unit": result["exponential_rate"],
                "local_drift_rate_per_model_time_unit": result["local_rate"],
                "exponential_rate_relative_error": result["exponential_relative_error"],
                "local_rate_relative_error": result["local_relative_error"],
                "rate_measurement_relative_difference": result["rate_relative_difference"],
                "exponential_log_ratio_rmse": result["exponential_rmse"],
                "local_drift_rmse": result["local_rmse"],
                "projection_relative_residual": result["projection_residual"],
                "maximum_absolute_pair_center_drift": result["maximum_absolute_pair_center_drift"],
                "minimum_boundary_edge_distance": result["minimum_boundary_edge_distance"],
                "maximum_boundary_candidates": result["maximum_boundary_candidates"],
                "sign_preserved": result["sign_preserved"],
                "receiving_sign_correct": result["receiving_sign_correct"],
                "software_version": VERSION,
            }
        )
    write_csv(RATE_PATH, list(rate_rows[0]), rate_rows)
    write_csv(RESPONSE_PATH, list(response_rows[0]), response_rows)
    return {
        "primary": primary,
        "grid": grid_rows,
        "rate_rows": rate_rows,
        "response_rows": response_rows,
        "zero_stationary_error": zero_stationary_error,
        "zero_coupling_maximum": zero_coupling_maximum,
    }


def _ensemble(
    configuration: dict[str, object],
    paths: int,
    steps: int,
    seed: int,
) -> dict[str, object]:
    grid, diffusion, sources, stationary, kernels, specification = _model(
        configuration, int(configuration["model"]["primary_grid_points"])
    )
    stochastic = configuration["stochastic_recovery"]
    base = _orthogonal_normal_inputs(paths, steps, seed)
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
            stationary,
            (0.0, 0.0),
            sources,
            _coupling_matrix(configuration),
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
            print(f"  completed corrected path {path_index + 1}/{paths}")
    prices = np.stack(price_paths)
    return {
        "prices": prices,
        "base": base,
        "delta_u": specification.delta_u,
        "minimum_edge": minimum_edge,
        "maximum_candidates": maximum_candidates,
    }


def _ratio_summary(
    numerators: np.ndarray, denominators: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    numerator = np.asarray(numerators, dtype=float)
    denominator = np.asarray(denominators, dtype=float)
    if numerator.ndim != 2 or denominator.shape != numerator.shape:
        raise ValueError("ratio components must share shape (groups, lags)")
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


def _curve_metrics(
    curve: np.ndarray, standard_error: np.ndarray, theory: np.ndarray
) -> tuple[float, float, float, float]:
    residual = curve - theory
    rmse = float(np.sqrt(np.mean(residual**2)))
    standardized = float(np.sqrt(np.mean((residual / standard_error) ** 2)))
    coverage = float(np.mean(np.abs(residual) <= 1.96 * standard_error))
    first_band = float(np.mean(curve[-10:-5]))
    second_band = float(np.mean(curve[-5:]))
    plateau_shift = abs(second_band - first_band) / abs(second_band)
    return rmse, standardized, coverage, plateau_shift


def _stochastic_recovery(configuration: dict[str, object]) -> dict[str, object]:
    stochastic = configuration["stochastic_recovery"]
    seconds_per_unit = float(configuration["model"]["seconds_per_model_time_unit"])
    step_seconds = float(configuration["model"]["operational_step_seconds"])
    steps = int(stochastic["total_operational_steps"])
    warm_up = int(stochastic["warm_up_steps"])
    print("Running independent normalization ensemble...")
    calibration = _ensemble(
        configuration,
        int(stochastic["calibration_paths"]),
        steps,
        int(stochastic["calibration_seed"]),
    )
    calibration_prices = calibration["prices"][:, warm_up:]
    calibration_seconds = np.asarray(stochastic["calibration_lags_seconds"], dtype=float)
    calibration_lags = np.rint(calibration_seconds / step_seconds).astype(int)
    calibration_centres = np.mean(calibration_prices, axis=2)
    calibration_counts = calibration_prices.shape[1] - calibration_lags
    calibration_square_sums = np.empty(
        (calibration_centres.shape[0], calibration_lags.size), dtype=float
    )
    for path_index, centre in enumerate(calibration_centres):
        for lag_index, lag in enumerate(calibration_lags):
            returns = centre[lag:] - centre[:-lag]
            calibration_square_sums[path_index, lag_index] = np.sum(returns**2)
    normalization_numerator = float(np.sum(calibration_square_sums))
    normalization_denominator = float(
        np.sum(
            np.broadcast_to(
                calibration_counts * calibration_seconds,
                calibration_square_sums.shape,
            )
        )
    )
    covariance_scale = normalization_numerator / normalization_denominator
    calibration_variance_rates = np.sum(calibration_square_sums, axis=0) / (
        calibration_centres.shape[0] * calibration_counts * calibration_seconds
    )
    calibration_scale_relative_range = float(
        (np.max(calibration_variance_rates) - np.min(calibration_variance_rates))
        / covariance_scale
    )

    print("Running holdout corrected-coupling ensemble...")
    validation = _ensemble(
        configuration,
        int(stochastic["validation_paths"]),
        steps,
        int(stochastic["validation_seed"]),
    )
    validation_prices = validation["prices"][:, warm_up:]
    lags_seconds = np.asarray(stochastic["validation_lags_seconds"], dtype=float)
    lag_steps = np.rint(lags_seconds / step_seconds).astype(int)
    components = np.stack(
        [return_component_sums(path, lag_steps) for path in validation_prices]
    )
    counts = validation_prices.shape[1] - lag_steps
    covariance_denominators = np.broadcast_to(
        counts * covariance_scale * lags_seconds,
        components[:, :, 0].shape,
    ).copy()
    covariance_curve, covariance_se = _ratio_summary(
        components[:, :, 0], covariance_denominators
    )
    correlation = pooled_correlation_summary(components)
    target_rate = float(configuration["coupling"]["target_total_rate_per_second"])
    covariance_theory = np.asarray(
        coupling_covariance_build_up(target_rate, lags_seconds)
    )
    correlation_theory = np.asarray(
        symmetric_closed_sde_correlation(target_rate, lags_seconds)
    )
    covariance_metrics = _curve_metrics(
        covariance_curve, covariance_se, covariance_theory
    )
    correlation_metrics = _curve_metrics(
        correlation.correlation,
        correlation.jackknife_standard_error,
        correlation_theory,
    )
    spreads = validation_prices[:, :, 0] - validation_prices[:, :, 1]
    predictor = spreads[:, :-1].ravel()
    increments = np.diff(spreads, axis=1).ravel()
    stochastic_rate_model = -float(np.dot(predictor, increments)) / (
        float(validation["delta_u"]) * float(np.dot(predictor, predictor))
    )
    stochastic_rate_seconds = stochastic_rate_model / seconds_per_unit
    input_correlation = float(
        np.corrcoef(validation["base"].reshape(-1, 2).T)[0, 1]
    )

    curve_rows = []
    for index, lag in enumerate(lags_seconds):
        curve_rows.append(
            {
                "target_id": configuration["target_id"],
                "lag_seconds": lag,
                "analytical_normalized_covariance": covariance_theory[index],
                "simulated_normalized_covariance": covariance_curve[index],
                "covariance_jackknife_standard_error": covariance_se[index],
                "covariance_normal_95_lower": covariance_curve[index] - 1.96 * covariance_se[index],
                "covariance_normal_95_upper": covariance_curve[index] + 1.96 * covariance_se[index],
                "analytical_exact_return_correlation": correlation_theory[index],
                "simulated_return_correlation": correlation.correlation[index],
                "correlation_jackknife_standard_error": correlation.jackknife_standard_error[index],
                "correlation_normal_95_lower": correlation.correlation[index] - 1.96 * correlation.jackknife_standard_error[index],
                "correlation_normal_95_upper": correlation.correlation[index] + 1.96 * correlation.jackknife_standard_error[index],
                "frozen_covariance_scale": covariance_scale,
                "target_rate_per_second": target_rate,
                "clock": "identity",
                "software_version": VERSION,
            }
        )
    write_csv(CURVE_PATH, list(curve_rows[0]), curve_rows)
    np.savez_compressed(
        PATH_ARCHIVE,
        operational_times_seconds=np.arange(validation_prices.shape[1], dtype=float)
        * step_seconds,
        validation_prices=validation_prices,
        validation_lag_steps=lag_steps,
        calibration_lag_steps=calibration_lags,
        frozen_covariance_scale=np.asarray(covariance_scale),
    )
    return {
        "curve_rows": curve_rows,
        "lags_seconds": lags_seconds,
        "covariance_theory": covariance_theory,
        "covariance_curve": covariance_curve,
        "covariance_se": covariance_se,
        "correlation_theory": correlation_theory,
        "correlation_curve": correlation.correlation,
        "correlation_se": correlation.jackknife_standard_error,
        "covariance_metrics": covariance_metrics,
        "correlation_metrics": correlation_metrics,
        "covariance_scale": covariance_scale,
        "calibration_variance_rates": calibration_variance_rates,
        "calibration_scale_relative_range": calibration_scale_relative_range,
        "stochastic_rate_model": stochastic_rate_model,
        "stochastic_rate_seconds": stochastic_rate_seconds,
        "input_correlation": input_correlation,
        "minimum_edge": min(calibration["minimum_edge"], validation["minimum_edge"]),
        "maximum_candidates": max(
            calibration["maximum_candidates"], validation["maximum_candidates"]
        ),
    }


def _check(
    check_id: str,
    check: str,
    observed,
    criterion: str,
    passed: bool,
) -> dict[str, object]:
    return {
        "check_id": check_id,
        "check": check,
        "observed": observed,
        "criterion": criterion,
        "status": "Verified" if passed else "Failed",
        "software_version": VERSION,
    }


def _plot(
    deterministic: dict[str, object],
    stochastic: dict[str, object],
    configuration: dict[str, object],
) -> None:
    lags = stochastic["lags_seconds"]
    figure, axes = plt.subplots(2, 2, figsize=(11.0, 7.8))

    axis = axes[0, 0]
    axis.fill_between(
        lags,
        stochastic["covariance_curve"] - 1.96 * stochastic["covariance_se"],
        stochastic["covariance_curve"] + 1.96 * stochastic["covariance_se"],
        color="#2166ac",
        alpha=0.17,
        label="Corrected simulation 95% jackknife band",
    )
    axis.plot(lags, stochastic["covariance_theory"], color="#111111", lw=2.0, label=r"$F(\kappa\Delta)$")
    axis.plot(lags, stochastic["covariance_curve"], color="#2166ac", lw=1.7, label="Normalized thick-boundary covariance")
    axis.set_ylim(0.0, 1.05)
    axis.set_xlabel(r"Identity-clock aggregation scale $\Delta t$ [s]")
    axis.set_ylabel("Normalized covariance response")
    axis.set_title("Paper envelope and corrected boundary simulation")
    axis.grid(alpha=0.18, linewidth=0.5)
    axis.legend(frameon=False, fontsize=7.5, loc="lower right")

    axis = axes[0, 1]
    axis.fill_between(
        lags,
        stochastic["correlation_curve"] - 1.96 * stochastic["correlation_se"],
        stochastic["correlation_curve"] + 1.96 * stochastic["correlation_se"],
        color="#b2182b",
        alpha=0.14,
        label="Corrected simulation 95% jackknife band",
    )
    axis.plot(lags, stochastic["correlation_theory"], color="#111111", lw=2.0, label="Exact closed-SDE correlation")
    axis.plot(lags, stochastic["correlation_curve"], color="#b2182b", lw=1.7, label="Thick-boundary return correlation")
    axis.set_ylim(0.0, 1.05)
    axis.set_xlabel(r"Identity-clock aggregation scale $\Delta t$ [s]")
    axis.set_ylabel("Realised return correlation")
    axis.set_title("Correlation estimand kept distinct")
    axis.grid(alpha=0.18, linewidth=0.5)
    axis.legend(frameon=False, fontsize=7.5, loc="lower right")

    axis = axes[1, 0]
    selected = (1, 3, 5, 7)
    for index in selected:
        result = deterministic["primary"][index]
        axis.plot(
            result["times"] * float(configuration["model"]["seconds_per_model_time_unit"]),
            result["coupled_spread"] / result["control_spread"],
            lw=1.2,
            label=rf"$z_0={result['initial_spread']:.3f}$",
        )
    time_seconds = deterministic["primary"][0]["times"] * float(
        configuration["model"]["seconds_per_model_time_unit"]
    )
    axis.plot(
        time_seconds,
        np.exp(-float(configuration["coupling"]["target_total_rate_per_second"]) * time_seconds),
        color="#111111",
        lw=2.0,
        ls="--",
        label=r"$e^{-0.025t}$",
    )
    axis.set_xlim(0.0, 80.0)
    axis.set_ylim(0.1, 1.02)
    axis.set_xlabel("Deterministic response time [s]")
    axis.set_ylabel(r"Paired spread ratio $z_\kappa/z_0$")
    axis.set_title("Signed thick-front relaxation")
    axis.grid(alpha=0.18, linewidth=0.5)
    axis.legend(frameon=False, fontsize=7.4, loc="upper right")

    axis = axes[1, 1]
    covariance_residual = stochastic["covariance_curve"] - stochastic["covariance_theory"]
    correlation_residual = stochastic["correlation_curve"] - stochastic["correlation_theory"]
    axis.axhline(0.0, color="#777777", lw=0.7)
    axis.plot(lags, covariance_residual, color="#2166ac", lw=1.5, label="Normalized covariance residual")
    axis.plot(lags, correlation_residual, color="#b2182b", lw=1.5, label="Return-correlation residual")
    axis.set_xlabel(r"Identity-clock aggregation scale $\Delta t$ [s]")
    axis.set_ylabel("Simulation minus theory")
    axis.set_title("Holdout conformity residuals")
    axis.grid(alpha=0.18, linewidth=0.5)
    axis.legend(frameon=False, fontsize=7.5, loc="best")

    figure.suptitle("Corrected coupling recovery on uniform operational time")
    figure.subplots_adjust(left=0.08, right=0.98, bottom=0.09, top=0.92, wspace=0.24, hspace=0.29)
    metadata = {
        "Creator": "correlation-emergence-v1.7.7",
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
    deterministic_policy = configuration["deterministic_recovery"]
    accepted_hashes = _accepted_hashes_valid(configuration)
    input_start_hashes = snapshot_hashes(configuration["accepted_inputs"])
    deterministic = _deterministic_recovery(configuration)
    primary = deterministic["primary"]
    maximum_exponential_error = max(
        float(row["exponential_relative_error"]) for row in primary
    )
    maximum_local_error = max(float(row["local_relative_error"]) for row in primary)
    maximum_measurement_difference = max(
        float(row["rate_relative_difference"]) for row in primary
    )
    deterministic_gate = bool(
        maximum_exponential_error
        <= float(policy["deterministic_rate_relative_error_maximum"])
        and maximum_local_error
        <= float(policy["deterministic_rate_relative_error_maximum"])
        and maximum_measurement_difference
        <= float(policy["deterministic_rate_measurement_relative_difference_maximum"])
        and max(float(row["projection_residual"]) for row in primary)
        <= float(deterministic_policy["maximum_projection_residual"])
        and max(float(row["maximum_absolute_pair_center_drift"]) for row in primary)
        <= float(deterministic_policy["maximum_absolute_pair_center_drift"])
        and all(bool(row["sign_preserved"]) for row in primary)
        and all(bool(row["receiving_sign_correct"]) for row in primary)
        and max(int(row["maximum_boundary_candidates"]) for row in primary) == 1
        and min(float(row["minimum_boundary_edge_distance"]) for row in primary)
        > float(deterministic_policy["minimum_boundary_edge_distance"])
    )
    if not deterministic_gate:
        raise RuntimeError(
            "deterministic corrected-coupling gate failed; stochastic execution forbidden"
        )
    stochastic = _stochastic_recovery(configuration)
    covariance_metrics = stochastic["covariance_metrics"]
    correlation_metrics = stochastic["correlation_metrics"]
    target_model_rate = float(
        configuration["coupling"]["target_total_rate_per_model_time_unit"]
    )
    stochastic_rate_error = abs(
        stochastic["stochastic_rate_model"] - target_model_rate
    ) / target_model_rate
    grid_errors = [float(row["exponential_relative_error"]) for row in deterministic["grid"]]
    comparator_hashes = {
        record["path"]: input_start_hashes[record["path"]]
        for record in configuration["accepted_inputs"]
        if record["role"].startswith("accepted_regularized")
    }
    comparator_immutable = not snapshot_errors(comparator_hashes)
    corrected_modules = configuration["architecture"]["implementation_split"]["corrected_target"]
    source_v1_unchanged = _sha256(
        PROJECT_ROOT / "source" / "source-v1" / "CATG-RD2Epps-v3-arXiv.tex"
    ) == next(
        record["sha256"]
        for record in configuration["accepted_inputs"]
        if record["role"] == "accepted_pre_audit_theory_source"
    )

    checks = [
        _check("S7CR-01", "accepted v1.7.6 input hashes", accepted_hashes, "all accepted hashes exact", accepted_hashes),
        _check("S7CR-02", "accepted parent", configuration["accepted_parent"], "exactly v1.7.6", configuration["accepted_parent"] == "v1.7.6"),
        _check("S7CR-03", "split corrected implementation", corrected_modules, "three distinct corrected operational modules", len(corrected_modules) == 3 and all((PROJECT_ROOT / path).is_file() for path in corrected_modules)),
        _check("S7CR-04", "regularized comparator immutability", comparator_immutable, "all accepted comparator hashes exact", comparator_immutable),
        _check("S7CR-05", "uniform operational dynamics", configuration["architecture"]["operational_dynamics"], "uniform_fixed_grid_only", configuration["architecture"]["operational_dynamics"] == "uniform_fixed_grid_only"),
        _check("S7CR-06", "identity-clock isolation", configuration["architecture"]["calendar_observation"], "identity_clock_only", configuration["architecture"]["calendar_observation"] == "identity_clock_only" and configuration["architecture"]["subordination"] == "not_active_in_this_component_gate"),
        _check("S7CR-07", "nonuniform update and interpolation excluded", f"{configuration['architecture']['legacy_nonuniform_state_update']}:{configuration['architecture']['calendar_interpolation']}", "both forbidden", configuration["architecture"]["legacy_nonuniform_state_update"] == "forbidden" and configuration["architecture"]["calendar_interpolation"] == "forbidden"),
        _check("S7CR-08", "explicit ordered rate type", configuration["architecture"]["production_type"], "TranslationModeCoupling", configuration["architecture"]["production_type"] == "TranslationModeCoupling"),
        _check("S7CR-09", "zero-spread coupling", deterministic["zero_coupling_maximum"], "exactly zero", deterministic["zero_coupling_maximum"] == 0.0),
        _check("S7CR-10", "zero-spread stationary state", deterministic["zero_stationary_error"], "maximum error <= 2e-12", deterministic["zero_stationary_error"] <= 2e-12),
        _check("S7CR-11", "receiving-book sign", all(bool(row["receiving_sign_correct"]) for row in primary), "correct for every signed perturbation", all(bool(row["receiving_sign_correct"]) for row in primary)),
        _check("S7CR-12", "deterministic exponential-rate recovery", maximum_exponential_error, f"maximum relative error <= {policy['deterministic_rate_relative_error_maximum']}", maximum_exponential_error <= float(policy["deterministic_rate_relative_error_maximum"])),
        _check("S7CR-13", "deterministic local-drift rate recovery", maximum_local_error, f"maximum relative error <= {policy['deterministic_rate_relative_error_maximum']}", maximum_local_error <= float(policy["deterministic_rate_relative_error_maximum"])),
        _check("S7CR-14", "independent rate-measurement agreement", maximum_measurement_difference, f"relative difference <= {policy['deterministic_rate_measurement_relative_difference_maximum']}", maximum_measurement_difference <= float(policy["deterministic_rate_measurement_relative_difference_maximum"])),
        _check("S7CR-15", "front-mode projection residual", max(float(row["projection_residual"]) for row in primary), f"maximum <= {deterministic_policy['maximum_projection_residual']}", max(float(row["projection_residual"]) for row in primary) <= float(deterministic_policy["maximum_projection_residual"])),
        _check("S7CR-16", "pair-centre preservation", max(float(row["maximum_absolute_pair_center_drift"]) for row in primary), f"maximum <= {deterministic_policy['maximum_absolute_pair_center_drift']}", max(float(row["maximum_absolute_pair_center_drift"]) for row in primary) <= float(deterministic_policy["maximum_absolute_pair_center_drift"])),
        _check("S7CR-17", "signed-spread preservation", all(bool(row["sign_preserved"]) for row in primary), "true for every response path", all(bool(row["sign_preserved"]) for row in primary)),
        _check("S7CR-18", "unique deterministic boundaries", max(int(row["maximum_boundary_candidates"]) for row in primary), "exactly one", max(int(row["maximum_boundary_candidates"]) for row in primary) == 1),
        _check("S7CR-19", "interior deterministic boundaries", min(float(row["minimum_boundary_edge_distance"]) for row in primary), f"strictly greater than {deterministic_policy['minimum_boundary_edge_distance']}", min(float(row["minimum_boundary_edge_distance"]) for row in primary) > float(deterministic_policy["minimum_boundary_edge_distance"])),
        _check("S7CR-20", "grid recovery sequence", grid_errors, "every registered grid has rate error <= 0.05", all(error <= float(policy["deterministic_rate_relative_error_maximum"]) for error in grid_errors)),
        _check("S7CR-21", "deterministic precondition", deterministic_gate, "passed before stochastic execution", deterministic_gate),
        _check("S7CR-22", "disjoint calibration and validation seeds", f"{configuration['stochastic_recovery']['calibration_seed']}:{configuration['stochastic_recovery']['validation_seed']}", "different seeds", int(configuration["stochastic_recovery"]["calibration_seed"]) != int(configuration["stochastic_recovery"]["validation_seed"])),
        _check("S7CR-23", "holdout input orthogonality", stochastic["input_correlation"], "absolute correlation <= 1e-14", abs(float(stochastic["input_correlation"])) <= 1e-14),
        _check("S7CR-24", "positive frozen covariance scale", stochastic["covariance_scale"], "finite and positive", np.isfinite(stochastic["covariance_scale"]) and stochastic["covariance_scale"] > 0.0),
        _check("S7CR-25", "normalized covariance absolute recovery", covariance_metrics[0], f"RMSE <= {policy['curve_absolute_rmse_maximum']}", covariance_metrics[0] <= float(policy["curve_absolute_rmse_maximum"])),
        _check("S7CR-26", "normalized covariance standardized recovery", covariance_metrics[1], f"standardized RMSE <= {policy['curve_standardized_rmse_maximum']}", covariance_metrics[1] <= float(policy["curve_standardized_rmse_maximum"])),
        _check("S7CR-27", "normalized covariance coverage", covariance_metrics[2], f"coverage >= {policy['minimum_pointwise_normal_95_coverage']}", covariance_metrics[2] >= float(policy["minimum_pointwise_normal_95_coverage"])),
        _check("S7CR-28", "normalized covariance plateau stability", covariance_metrics[3], f"relative shift <= {policy['plateau_relative_shift_maximum']}", covariance_metrics[3] <= float(policy["plateau_relative_shift_maximum"])),
        _check("S7CR-29", "exact return-correlation absolute recovery", correlation_metrics[0], f"RMSE <= {policy['curve_absolute_rmse_maximum']}", correlation_metrics[0] <= float(policy["curve_absolute_rmse_maximum"])),
        _check("S7CR-30", "exact return-correlation standardized recovery", correlation_metrics[1], f"standardized RMSE <= {policy['curve_standardized_rmse_maximum']}", correlation_metrics[1] <= float(policy["curve_standardized_rmse_maximum"])),
        _check("S7CR-31", "exact return-correlation coverage", correlation_metrics[2], f"coverage >= {policy['minimum_pointwise_normal_95_coverage']}", correlation_metrics[2] >= float(policy["minimum_pointwise_normal_95_coverage"])),
        _check("S7CR-32", "stochastic spread-rate diagnostic", stochastic_rate_error, f"relative error <= {configuration['stochastic_recovery']['stochastic_rate_diagnostic_relative_error_maximum']}", stochastic_rate_error <= float(configuration["stochastic_recovery"]["stochastic_rate_diagnostic_relative_error_maximum"])),
        _check("S7CR-33", "stochastic boundary validity", (stochastic["minimum_edge"], stochastic["maximum_candidates"]), "unique and minimum edge distance > 8", stochastic["maximum_candidates"] == 1 and stochastic["minimum_edge"] > 8.0),
        _check("S7CR-34", "paper source-v1 freeze", source_v1_unchanged, "accepted source-v1 hash exact", source_v1_unchanged),
        _check("S7CR-35", "theory qualification recorded", configuration["theory_conformity"]["paper_status"], "reduced response retained and source-to-rate bridge qualified", configuration["theory_conformity"]["paper_status"] == "reduced_response_retained_regularized_source_to_rate_bridge_requires_qualification"),
        _check("S7CR-36", "combined prediction remains unfitted", configuration["architecture"]["combined_curve_refit"], "forbidden and not executed", configuration["architecture"]["combined_curve_refit"] == "forbidden" and configuration["stage_boundary"]["combined_prediction_executed"] is False),
        _check("S7CR-37", "pair-centre variance normalization stability", stochastic["calibration_scale_relative_range"], f"relative range <= {configuration['stochastic_recovery']['calibration_variance_rate_relative_range_maximum']}", stochastic["calibration_scale_relative_range"] <= float(configuration["stochastic_recovery"]["calibration_variance_rate_relative_range_maximum"])),
    ]
    _plot(deterministic, stochastic, configuration)
    output_contract = configuration["output_contract"]
    checks.append(
        _check(
            "S7CR-38",
            "Figure 8 and output contract",
            (len(stochastic["curve_rows"]), len(deterministic["rate_rows"]), len(deterministic["response_rows"])),
            "20 curve rows, 11 rate rows, 1288 response rows and figure pair",
            len(stochastic["curve_rows"]) == int(output_contract["curve_rows"])
            and len(deterministic["rate_rows"])
            == int(output_contract["deterministic_primary_rate_rows"])
            + int(output_contract["grid_convergence_rows"])
            and len(deterministic["response_rows"]) == 1288
            and FIGURE_STEM.with_suffix(".pdf").is_file()
            and FIGURE_STEM.with_suffix(".png").is_file()
            and PATH_ARCHIVE.is_file(),
        )
    )
    failures = [row for row in checks if row["status"] == "Failed"]
    result_label = "recovered" if not failures else "qualified_nonconformity"
    summary_rows = [
        {
            "target_id": configuration["target_id"],
            "result_label": result_label,
            "deterministic_gate": "passed" if deterministic_gate else "failed",
            "maximum_exponential_rate_relative_error": maximum_exponential_error,
            "maximum_local_rate_relative_error": maximum_local_error,
            "normalized_covariance_rmse": covariance_metrics[0],
            "normalized_covariance_standardized_rmse": covariance_metrics[1],
            "normalized_covariance_coverage": covariance_metrics[2],
            "normalized_covariance_plateau_shift": covariance_metrics[3],
            "return_correlation_rmse": correlation_metrics[0],
            "return_correlation_standardized_rmse": correlation_metrics[1],
            "return_correlation_coverage": correlation_metrics[2],
            "stochastic_rate_per_model_time_unit": stochastic["stochastic_rate_model"],
            "frozen_covariance_scale": stochastic["covariance_scale"],
            "calibration_variance_rate_relative_range": stochastic["calibration_scale_relative_range"],
            "paper_consequence": configuration["theory_conformity"]["paper_status"],
            "next_stage": configuration["stage_boundary"]["next_stage_on_acceptance"],
            "software_version": VERSION,
        }
    ]
    write_csv(SUMMARY_PATH, list(summary_rows[0]), summary_rows)
    write_csv(CHECK_PATH, list(checks[0]), checks)
    for row in checks:
        print(f"{row['check_id']}: {row['status']} - {row['check']}")
    print(
        f"Corrected coupling recovery completed: {len(checks) - len(failures)} "
        f"checks verified, {len(failures)} failures; result {result_label}."
    )
    print(
        "Figure 8 generated; the regularized comparator and source-v1 paper "
        "remain frozen, and the combined prediction remains blocked until v1.7.8."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
