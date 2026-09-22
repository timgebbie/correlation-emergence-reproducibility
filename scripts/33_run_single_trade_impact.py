"""Run the v1.8.1 paired single-trade own/cross-impact experiment."""

from __future__ import annotations

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

from functions.events import (
    EVENT_MARKET_ORDER,
    OrderEvent,
    ground_truth_aggressor_sign,
    operational_translation_single_event_pair,
    quote_midpoint_sign,
)
from functions.figure_io import atomic_savefig, remove_orphaned_figure_staging_files
from functions.integrity import accepted_input_errors, snapshot_errors, snapshot_hashes
from functions.io_utils import write_csv
from functions.observation import (
    poisson_refresh_path_from_uniforms,
    subordinate_two_book_previous_refresh,
)
from functions.operational import (
    OperationalSolverSpec,
    OperationalSource,
    TranslationModeCoupling,
    TwoBookInnovationPolicy,
    apply_spatial_boundary,
    operational_sibuya_kernel,
    operational_source_density,
    stationary_density,
)


VERSION = "1.8.1"
CONFIG_PATH = PROJECT_ROOT / "config" / "config-v1.8.1.json"
CHECK_PATH = PROJECT_ROOT / "diagnostics" / "single-trade-impact-checks-v1.8.csv"
CURVE_PATH = PROJECT_ROOT / "outputs" / "single-trade-impact-curves-v1.8.csv"
MEMBER_PATH = PROJECT_ROOT / "outputs" / "single-trade-impact-members-v1.8.csv"
EVENT_PATH = PROJECT_ROOT / "outputs" / "single-trade-impact-events-v1.8.csv"
CLOCK_PATH = PROJECT_ROOT / "outputs" / "single-trade-impact-clock-rates-v1.8.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "single-trade-impact-summary-v1.8.csv"
PATH_ARCHIVE = PROJECT_ROOT / "outputs" / "single-trade-impact-paths-v1.8.npz"
FIGURE_STEM = PROJECT_ROOT / "figures" / "figure-09-single-trade-impact-v2"


def _load_configuration() -> dict[str, object]:
    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if configuration.get("schema_version") != VERSION:
        raise ValueError("single-trade impact configuration version mismatch")
    if configuration["architecture"]["operational_dynamics"] != "uniform_fixed_grid_only":
        raise ValueError("v1.8.1 requires uniform operational dynamics")
    return configuration


def _model(configuration: dict[str, object]):
    model = configuration["model"]
    grid = np.linspace(
        float(model["grid_lower"]),
        float(model["grid_upper"]),
        int(model["grid_points"]),
    )
    delta_x = float(grid[1] - grid[0])
    diffusion = tuple(float(value) for value in model["diffusion"])
    transport = float(model["transport_probability"])
    delta_u = transport * delta_x**2 / (2.0 * diffusion[0])
    if not np.isclose(delta_u, float(model["operational_step_model_units"])):
        raise ValueError("declared operational step does not match the lattice")
    sources = tuple(
        OperationalSource(
            float(model["source_lambda"][book]),
            float(model["source_mu"][book]),
        )
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
        delta_u=delta_u,
        transport_probability=transport,
        cancellation_rates=tuple(float(value) for value in model["cancellation_rates"]),
        minimum_abs_boundary_slope=float(model["minimum_abs_boundary_slope"]),
    )
    rates = model["ordered_coupling_rates_per_model_time_unit"]
    couplings = (
        (None, TranslationModeCoupling(float(rates[0]))),
        (TranslationModeCoupling(float(rates[1])), None),
    )
    policy = TwoBookInnovationPolicy(
        float(model["innovation_sigma"][0]),
        float(model["innovation_sigma"][1]),
        float(model["microscopic_innovation_correlation"]),
    )
    return grid, diffusion, sources, stationary, kernels, specification, couplings, policy


def _symmetry_controlled_inputs(configuration: dict[str, object]) -> np.ndarray:
    experiment = configuration["experiment"]
    primitive_paths = int(experiment["primitive_random_paths"])
    steps = int(experiment["total_operational_steps"])
    raw = np.random.default_rng(int(experiment["operational_seed"])).standard_normal(
        (primitive_paths, steps, 2)
    )
    flat = raw.reshape(-1, 2)
    first = flat[:, 0]
    second = flat[:, 1]
    first -= np.mean(first)
    second -= np.mean(second)
    first *= np.sqrt(first.size / np.dot(first, first))
    second -= first * np.dot(first, second) / np.dot(first, first)
    second *= np.sqrt(second.size / np.dot(second, second))
    primitive = np.stack((first, second), axis=1).reshape(primitive_paths, steps, 2)
    result = np.concatenate(
        (primitive, -primitive, primitive[:, :, ::-1], -primitive[:, :, ::-1]),
        axis=0,
    )
    if result.shape[0] != int(experiment["paths"]):
        raise ValueError("symmetry construction does not match declared path count")
    result.setflags(write=False)
    return result


def _refresh_pairs(configuration: dict[str, object], horizon: float):
    experiment = configuration["experiment"]
    paths = int(experiment["paths"])
    uniforms_per_book = int(experiment["clock_uniforms_per_book_path"])
    primitive = np.random.default_rng(int(experiment["clock_seed"])).random(
        (paths // 2, 2, uniforms_per_book)
    )
    rates = tuple(float(value) for value in experiment["book_refresh_rates_per_second"])
    result = []
    for path in range(paths):
        values = primitive[path] if path < paths // 2 else primitive[path - paths // 2, ::-1]
        result.append(
            tuple(
                poisson_refresh_path_from_uniforms(
                    values[book],
                    rates[book],
                    horizon,
                    stream_id=f"v1.8.1-path-{path:02d}-book-{book + 1}",
                )
                for book in range(2)
            )
        )
    return tuple(result)


def _relative_difference(first: np.ndarray, second: np.ndarray) -> float:
    a = np.asarray(first, dtype=float)
    b = np.asarray(second, dtype=float)
    scale = np.maximum(np.maximum(np.abs(a), np.abs(b)), 1e-8)
    supported = scale > 1e-6
    return float(np.max(np.abs(a[supported] - b[supported]) / scale[supported]))


def _domain_scaled_side_difference(
    side_means: np.ndarray,
    buy_index: int,
    sell_index: int,
) -> float:
    """Return a stable buy/sell discrepancy on each domain's impact scale.

    Cellwise relative error is ill-conditioned when calendar cross-impact is
    close to zero.  For each measurement domain, normalize the largest
    absolute buy/sell difference by the peak side-averaged own impact in that
    domain, then take the maximum across domains.
    """

    values = np.asarray(side_means, dtype=float)
    if values.ndim != 5 or values.shape[0] != 2 or values.shape[1] != 2:
        raise ValueError("side_means must have shape (2, 2, domains, lags, 2)")
    ratios: list[float] = []
    for domain_index in range(values.shape[2]):
        buy = values[:, buy_index, domain_index]
        sell = values[:, sell_index, domain_index]
        maximum_difference = float(np.max(np.abs(buy - sell)))
        own_scale = max(
            float(
                np.max(
                    0.5
                    * (
                        np.abs(values[book, buy_index, domain_index, :, book])
                        + np.abs(values[book, sell_index, domain_index, :, book])
                    )
                )
            )
            for book in range(2)
        )
        if own_scale <= 0.0:
            raise ValueError("buy/sell normalization requires positive own impact")
        ratios.append(maximum_difference / own_scale)
    return max(ratios)


def _check(
    check_id: str,
    check: str,
    observed: object,
    criterion: str,
    passed: bool,
) -> dict[str, object]:
    if isinstance(observed, (dict, list, tuple, set, np.ndarray)):
        if isinstance(observed, np.ndarray):
            observed = observed.tolist()
        elif isinstance(observed, set):
            observed = sorted(observed)
        observed = json.dumps(observed, sort_keys=True)
    return {
        "check_id": check_id,
        "check": check,
        "observed": observed,
        "criterion": criterion,
        "status": "Verified" if passed else "Failed",
        "software_version": VERSION,
    }


def _run_experiment(
    configuration: dict[str, object], *, write_outputs: bool = True
) -> dict[str, object]:
    experiment = configuration["experiment"]
    model = configuration["model"]
    paths = int(experiment["paths"])
    steps = int(experiment["total_operational_steps"])
    event_step = int(experiment["event_operational_step"])
    quantity = float(experiment["event_quantity"])
    sides = tuple(int(value) for value in experiment["event_sides"])
    event_books = tuple(int(value) for value in experiment["event_books"])
    lags_seconds = np.asarray(experiment["response_lags_seconds"], dtype=float)
    step_seconds = float(model["operational_step_seconds"])
    lag_steps = np.rint(lags_seconds / step_seconds).astype(int)
    if np.any(np.abs(lag_steps * step_seconds - lags_seconds) > 1e-12):
        raise ValueError("response lags must lie on the operational grid")
    if event_step + int(np.max(lag_steps)) > steps:
        raise ValueError("response lags exceed the path after the event")

    grid, diffusion, sources, stationary, kernels, spec, couplings, policy = _model(configuration)
    base_inputs = _symmetry_controlled_inputs(configuration)
    operational_times_seconds = np.arange(steps + 1, dtype=float) * step_seconds
    refresh_pairs = _refresh_pairs(configuration, float(operational_times_seconds[-1]))

    responses = np.empty((paths, 2, 2, 2, lags_seconds.size, 2), dtype=float)
    active = np.ones_like(responses)
    control_prices = np.empty((paths, steps + 1, 2), dtype=float)
    shocked_prices = np.empty((paths, 2, 2, steps + 1, 2), dtype=float)
    calendar_control = np.empty_like(control_prices)
    calendar_shocked = np.empty_like(shocked_prices)
    calendar_indices = np.empty((paths, steps + 1, 2), dtype=np.int64)
    event_rows: list[dict[str, object]] = []
    member_rows: list[dict[str, object]] = []
    clock_rows: list[dict[str, object]] = []
    pre_event_maximum = 0.0
    minimum_edge = math.inf
    maximum_candidates = 0
    event_mass_errors: list[float] = []
    execution_side_products: list[float] = []

    for path_index in range(paths):
        path_control_written = False
        sampled_control_written = False
        for event_book in event_books:
            for side_index, side in enumerate(sides):
                event = OrderEvent(
                    event_id=f"v181-p{path_index:02d}-b{event_book + 1}-s{side:+d}",
                    event_type=EVENT_MARKET_ORDER,
                    book_index=event_book,
                    operational_step=event_step,
                    side=side,
                    quantity=quantity,
                )
                pair = operational_translation_single_event_pair(
                    grid,
                    stationary,
                    (0.0, 0.0),
                    sources,
                    couplings,
                    kernels,
                    base_inputs[path_index],
                    policy,
                    diffusion,
                    spec,
                    event,
                )
                if not path_control_written:
                    control_prices[path_index] = pair.control_prices
                    path_control_written = True
                elif not np.array_equal(control_prices[path_index], pair.control_prices):
                    raise RuntimeError("common-input control path changed across event scenarios")
                shocked_prices[path_index, event_book, side_index] = pair.shocked_prices
                pre_event_maximum = max(
                    pre_event_maximum,
                    float(np.max(np.abs(pair.paired_price_difference[:event_step]))),
                )
                minimum_edge = min(
                    minimum_edge, float(np.min(pair.shocked_boundary_edge_distances))
                )
                maximum_candidates = max(
                    maximum_candidates, int(np.max(pair.shocked_boundary_candidate_counts))
                )
                application = pair.event_application
                dx = float(grid[1] - grid[0])
                applied_mass = dx * float(np.sum(np.abs(application.density_delta)))
                event_mass_errors.append(abs(applied_mass - quantity))
                execution_side_products.append(
                    side * (float(application.execution_log_price) - application.pre_event_mid_log_price)
                )
                event_rows.append(
                    {
                        "event_id": event.event_id,
                        "path_index": path_index,
                        "event_book": event_book,
                        "side": side,
                        "quantity": quantity,
                        "filled_quantity": application.filled_quantity,
                        "pre_event_mid_log_price": application.pre_event_mid_log_price,
                        "execution_log_price_proxy": application.execution_log_price,
                        "affected_grid_indices": json.dumps(application.affected_grid_indices),
                        "applied_density_mass": applied_mass,
                        "ground_truth_aggressor_sign": ground_truth_aggressor_sign(application),
                        "quote_midpoint_sign": quote_midpoint_sign(application),
                        "event_operational_step": event_step,
                        "event_operational_time_seconds": operational_times_seconds[event_step],
                        "software_version": VERSION,
                    }
                )

                sampled_control = subordinate_two_book_previous_refresh(
                    operational_times_seconds,
                    pair.control_prices,
                    refresh_pairs[path_index],
                    operational_times_seconds,
                )
                sampled_shocked = subordinate_two_book_previous_refresh(
                    operational_times_seconds,
                    pair.shocked_prices,
                    refresh_pairs[path_index],
                    operational_times_seconds,
                )
                if not sampled_control_written:
                    calendar_control[path_index] = sampled_control.prices
                    calendar_indices[path_index] = sampled_control.operational_indices
                    sampled_control_written = True
                elif not np.array_equal(calendar_control[path_index], sampled_control.prices):
                    raise RuntimeError("calendar control changed across event scenarios")
                calendar_shocked[path_index, event_book, side_index] = sampled_shocked.prices

                operational_signed = pair.signed_price_response[event_step + lag_steps]
                calendar_signed = side * (
                    sampled_shocked.prices[event_step + lag_steps]
                    - sampled_control.prices[event_step + lag_steps]
                )
                responses[path_index, event_book, side_index, 0] = operational_signed
                responses[path_index, event_book, side_index, 1] = calendar_signed
                active[path_index, event_book, side_index, 1] = (
                    sampled_control.operational_indices[event_step + lag_steps] >= event_step
                ).astype(float)

        for book, clock in enumerate(refresh_pairs[path_index]):
            clock_rows.append(
                {
                    "path_index": path_index,
                    "book_index": book,
                    "stream_id": clock.stream_id,
                    "input_rate_per_second": clock.input_rate,
                    "measured_rate_per_second": clock.measured_rate,
                    "retained_waiting_intervals": clock.waiting_intervals.size,
                    "supported_horizon_seconds": clock.supported_horizon,
                    "software_version": VERSION,
                }
            )
        if (path_index + 1) % 2 == 0 or path_index + 1 == paths:
            print(f"  completed single-trade path {path_index + 1}/{paths}")

    curve_rows: list[dict[str, object]] = []
    curve_mean = np.empty((2, 2, 2, lags_seconds.size), dtype=float)
    curve_se = np.empty_like(curve_mean)
    curve_active = np.empty_like(curve_mean)
    for event_book in event_books:
        for response_book in range(2):
            impact_type = "own" if event_book == response_book else "cross"
            for domain_index, domain in enumerate(("operational", "calendar")):
                path_side_means = np.mean(
                    responses[:, event_book, :, domain_index, :, response_book], axis=1
                )
                means = np.mean(path_side_means, axis=0)
                standard_errors = np.std(path_side_means, axis=0, ddof=1) / np.sqrt(paths)
                active_fractions = np.mean(
                    active[:, event_book, :, domain_index, :, response_book], axis=(0, 1)
                )
                curve_mean[event_book, response_book, domain_index] = means
                curve_se[event_book, response_book, domain_index] = standard_errors
                curve_active[event_book, response_book, domain_index] = active_fractions
                for lag_index, lag in enumerate(lags_seconds):
                    curve_rows.append(
                        {
                            "target_id": configuration["target_id"],
                            "measurement_domain": domain,
                            "event_book": event_book,
                            "response_book": response_book,
                            "impact_type": impact_type,
                            "lag_seconds": lag,
                            "mean_signed_log_mid_impact": means[lag_index],
                            "standard_error": standard_errors[lag_index],
                            "normal_95_lower": means[lag_index] - 1.96 * standard_errors[lag_index],
                            "normal_95_upper": means[lag_index] + 1.96 * standard_errors[lag_index],
                            "mean_impact_per_unit_quantity": means[lag_index] / quantity,
                            "active_observation_fraction": active_fractions[lag_index],
                            "paths": paths,
                            "sides_per_path": len(sides),
                            "event_quantity": quantity,
                            "software_version": VERSION,
                        }
                    )
                for path_index in range(paths):
                    for side_index, side in enumerate(sides):
                        for lag_index, lag in enumerate(lags_seconds):
                            value = responses[
                                path_index,
                                event_book,
                                side_index,
                                domain_index,
                                lag_index,
                                response_book,
                            ]
                            member_rows.append(
                                {
                                    "path_index": path_index,
                                    "measurement_domain": domain,
                                    "event_book": event_book,
                                    "response_book": response_book,
                                    "impact_type": impact_type,
                                    "event_side": side,
                                    "lag_seconds": lag,
                                    "signed_log_mid_impact": value,
                                    "impact_per_unit_quantity": value / quantity,
                                    "active_observation": active[
                                        path_index,
                                        event_book,
                                        side_index,
                                        domain_index,
                                        lag_index,
                                        response_book,
                                    ],
                                    "software_version": VERSION,
                                }
                            )

    input_flat = base_inputs.reshape(-1, 2)
    input_correlation = float(np.corrcoef(input_flat.T)[0, 1])
    side_means = np.mean(responses, axis=0)
    buy_index = sides.index(1)
    sell_index = sides.index(-1)
    side_local_relative_difference = _relative_difference(
        side_means[:, buy_index], side_means[:, sell_index]
    )
    side_difference = _domain_scaled_side_difference(
        side_means,
        buy_index,
        sell_index,
    )
    book_difference = max(
        _relative_difference(curve_mean[0, 0], curve_mean[1, 1]),
        _relative_difference(curve_mean[0, 1], curve_mean[1, 0]),
    )
    lag_zero = int(np.flatnonzero(np.isclose(lags_seconds, 0.0))[0])
    lag_twenty = int(np.flatnonzero(np.isclose(lags_seconds, 20.0))[0])
    lag_forty = int(np.flatnonzero(np.isclose(lags_seconds, 40.0))[0])
    lag_long = -1
    operational_own_zero = float(np.mean([curve_mean[0, 0, 0, lag_zero], curve_mean[1, 1, 0, lag_zero]]))
    operational_cross_twenty = float(np.mean([curve_mean[0, 1, 0, lag_twenty], curve_mean[1, 0, 0, lag_twenty]]))
    operational_cross_zero = float(np.max(np.abs([curve_mean[0, 1, 0, lag_zero], curve_mean[1, 0, 0, lag_zero]])))
    calendar_active_zero = float(np.mean([curve_active[0, 0, 1, lag_zero], curve_active[1, 1, 1, lag_zero]]))
    calendar_active_forty = float(np.min(curve_active[:, :, 1, lag_forty]))
    calendar_own_forty = float(np.mean([curve_mean[0, 0, 1, lag_forty], curve_mean[1, 1, 1, lag_forty]]))
    own_long = float(np.mean([curve_mean[0, 0, 0, lag_long], curve_mean[1, 1, 0, lag_long]]))
    cross_long = float(np.mean([curve_mean[0, 1, 0, lag_long], curve_mean[1, 0, 0, lag_long]]))
    long_ratio = own_long / cross_long
    measured_rates = np.asarray([row["measured_rate_per_second"] for row in clock_rows])
    input_rates = np.asarray([row["input_rate_per_second"] for row in clock_rows])
    clock_relative_error = float(np.max(np.abs(measured_rates - input_rates) / input_rates))
    distinct_clock_pairs = all(
        refresh_pairs[path][0].stream_id != refresh_pairs[path][1].stream_id
        and not np.array_equal(
            refresh_pairs[path][0].waiting_intervals,
            refresh_pairs[path][1].waiting_intervals,
        )
        for path in range(paths)
    )

    if write_outputs:
        write_csv(CURVE_PATH, list(curve_rows[0]), curve_rows)
        write_csv(MEMBER_PATH, list(member_rows[0]), member_rows)
        write_csv(EVENT_PATH, list(event_rows[0]), event_rows)
        write_csv(CLOCK_PATH, list(clock_rows[0]), clock_rows)
        np.savez_compressed(
            PATH_ARCHIVE,
            base_standard_normals=base_inputs,
            operational_times_seconds=operational_times_seconds,
            control_prices=control_prices,
            shocked_prices=shocked_prices,
            calendar_query_times_seconds=operational_times_seconds,
            calendar_control_prices=calendar_control,
            calendar_shocked_prices=calendar_shocked,
            calendar_operational_indices=calendar_indices,
            response_lags_seconds=lags_seconds,
            response_lag_steps=lag_steps,
            event_operational_step=np.asarray(event_step),
            event_quantity=np.asarray(quantity),
        )
    return {
        "base_inputs": base_inputs,
        "responses": responses,
        "active": active,
        "curve_rows": curve_rows,
        "member_rows": member_rows,
        "event_rows": event_rows,
        "clock_rows": clock_rows,
        "curve_mean": curve_mean,
        "curve_se": curve_se,
        "curve_active": curve_active,
        "lags_seconds": lags_seconds,
        "input_correlation": input_correlation,
        "pre_event_maximum": pre_event_maximum,
        "minimum_edge": minimum_edge,
        "maximum_candidates": maximum_candidates,
        "event_mass_error": max(event_mass_errors),
        "minimum_execution_side_product": min(execution_side_products),
        "side_difference": side_difference,
        "side_local_relative_difference": side_local_relative_difference,
        "book_difference": book_difference,
        "operational_own_zero": operational_own_zero,
        "operational_cross_zero": operational_cross_zero,
        "operational_cross_twenty": operational_cross_twenty,
        "calendar_active_zero": calendar_active_zero,
        "calendar_active_forty": calendar_active_forty,
        "calendar_own_forty": calendar_own_forty,
        "long_ratio": long_ratio,
        "clock_relative_error": clock_relative_error,
        "distinct_clock_pairs": distinct_clock_pairs,
        "control_prices": control_prices,
        "shocked_prices": shocked_prices,
        "calendar_control": calendar_control,
        "calendar_shocked": calendar_shocked,
        "calendar_indices": calendar_indices,
    }


def _plot(result: dict[str, object], configuration: dict[str, object]) -> None:
    lags = result["lags_seconds"]
    means = result["curve_mean"]
    errors = result["curve_se"]
    figure, axes = plt.subplots(2, 2, figsize=(10.8, 8.2), sharex=True, sharey=True)
    maximum = 0.0
    minimum = 0.0
    for event_book in range(2):
        for response_book in range(2):
            for domain in range(2):
                maximum = max(maximum, float(np.max(means[event_book, response_book, domain] + 1.96 * errors[event_book, response_book, domain])))
                minimum = min(minimum, float(np.min(means[event_book, response_book, domain] - 1.96 * errors[event_book, response_book, domain])))
    margin = 0.08 * max(maximum - minimum, 1e-6)
    common_limits = (minimum - margin, maximum + margin)

    for event_book in range(2):
        for response_book in range(2):
            axis = axes[event_book, response_book]
            for domain, color, label in (
                (0, "#2166ac", "Operational paired impact"),
                (1, "#d6604d", "After previous-refresh subordination"),
            ):
                mean = means[event_book, response_book, domain]
                error = errors[event_book, response_book, domain]
                axis.fill_between(
                    lags,
                    mean - 1.96 * error,
                    mean + 1.96 * error,
                    color=color,
                    alpha=0.14,
                )
                axis.plot(lags, mean, color=color, lw=1.7, label=label)
            impact_type = "own impact" if event_book == response_book else "cross impact"
            axis.axhline(0.0, color="#777777", lw=0.7)
            axis.set_title(
                f"Event book {event_book + 1} → response book {response_book + 1} ({impact_type})"
            )
            axis.set_ylim(*common_limits)
            axis.grid(alpha=0.18, linewidth=0.5)
            if event_book == 1:
                axis.set_xlabel("Lag after market event [s]")
            if response_book == 0:
                axis.set_ylabel("Aggressor-signed log-mid response")
            if event_book == 0 and response_book == 0:
                axis.legend(frameon=False, fontsize=7.7, loc="upper right")

    figure.suptitle(
        "Paired single-trade own and cross impact: operational dynamics then explicit subordination"
    )
    figure.subplots_adjust(left=0.09, right=0.98, bottom=0.08, top=0.91, wspace=0.12, hspace=0.20)
    metadata = {
        "Creator": "correlation-emergence-v1.8.1",
        "CreationDate": None,
        "ModDate": None,
    }
    atomic_savefig(figure, FIGURE_STEM.with_suffix(".pdf"), metadata=metadata)
    atomic_savefig(figure, FIGURE_STEM.with_suffix(".png"), dpi=200)
    plt.close(figure)


def _resolution_model(dx=.1):
    cfg = json.loads(CONFIG_PATH.read_text())
    cfg['model']['grid_points'] = round(20 / dx) + 1
    cfg['model']['operational_step_model_units'] = .5 * dx * dx
    cfg['model']['operational_step_seconds'] = 50 * dx * dx
    cfg['model']['innovation_sigma'] = [.4 * .1 / dx] * 2
    return _model(cfg)


def _resolution_paths(z, dx=0.1, tapes=None, initial=None, initial_prices=None, event_records=None):
    from functions.events.records import apply_order_event
    from functions.operational.boundary import extract_reaction_boundary
    grid, diff, sources, stationary, kernels, spec, couplings, policy = _resolution_model(dx)
    n, steps, _ = z.shape
    density = np.broadcast_to(stationary, (n,) + stationary.shape).copy() if initial is None else np.array(initial, copy=True)
    prices = np.zeros((n, steps + 1, 2))
    if initial_prices is not None:
        prices[:, 0] = initial_prices
    actual = float(grid[1] - grid[0])
    du = spec.delta_u
    sigma = 0.4 * 0.1 / dx
    left = np.zeros_like(density)
    right = np.zeros_like(density)
    events = {}
    if tapes is not None:
        assert len(tapes) == n
        for path, tape in enumerate(tapes):
            for e in tape:
                events.setdefault(e.operational_step, []).append((path, e))
    min_slope = float('inf')
    edge = 10.0
    mass_error = 0.0
    events_applied = 0
    fallbacks = 0
    for k in range(steps):
        old = prices[:, k, :]
        for path, e in events.get(k + 1, []):
            app = apply_order_event(e, grid, density[path, e.book_index], pre_event_mid_log_price=float(old[path, e.book_index]))
            if event_records is not None:
                from functions.events import quote_midpoint_sign
                event_records.append((path, e.book_index, e.operational_step, e.side, float(app.execution_log_price), quote_midpoint_sign(app)))
            density[path, e.book_index] += app.density_delta
            mass_error = max(mass_error, abs(actual * np.sum(np.abs(app.density_delta)) - e.quantity))
            events_applied += 1
        disp = grid[None, None, :] - old[:, :, None]
        src = -0.1 * disp * np.exp(-0.1 * disp * disp)
        grad = np.gradient(density, grid, axis=-1, edge_order=2)
        coupling = 1.25 * (old - old[:, ::-1])[:, :, None] * grad
        coupling[:, :, [0, -1]] = 0.0
        bias = 0.5 * np.tanh(sigma * z[:, k, :] * actual / 2.0)
        left[..., 1:] = density[..., :-1]
        right[..., :-1] = density[..., 1:]
        history = (0.5 * (0.5 + bias))[:, :, None] * left + (0.5 * (0.5 - bias))[:, :, None] * right - 0.5 * density
        density = history + density + du * (src + coupling)
        density[:, :, [0, -1]] = 0.0
        slopes = np.diff(density, axis=-1) / actual
        cross = (density[..., :-1] * density[..., 1:] < 0) & (np.abs(slopes) >= 1e-06)
        exslopes = (density[..., 2:] - density[..., :-2]) / (2 * actual)
        zeros = (density[..., 1:-1] == 0) & (density[..., :-2] * density[..., 2:] < 0) & (np.abs(exslopes) >= 1e-06)
        counts = cross.sum(axis=-1) + zeros.sum(axis=-1)
        if not np.isfinite(density).all():
            raise RuntimeError('Nonfinite density')
        indices = np.argmax(cross, axis=-1)
        lv = np.take_along_axis(density, indices[..., None], axis=-1)[..., 0]
        slope = np.take_along_axis(slopes, indices[..., None], axis=-1)[..., 0]
        use = cross.any(axis=-1)
        ix = np.argmax(zeros, axis=-1)
        chosen = np.where(use, slope, np.take_along_axis(exslopes, ix[..., None], axis=-1)[..., 0])
        p = np.where(use, grid[indices] - lv / np.where(use, slope, 1.0), grid[ix + 1])
        for a, b in np.argwhere(counts != 1):
            boundary = extract_reaction_boundary(grid, density[a, b], selection=spec.boundary_selection, previous_price=float(old[a, b]) if spec.boundary_selection == 'nearest_previous' else None, minimum_abs_slope=spec.minimum_abs_boundary_slope)
            p[a, b] = boundary.price
            fallbacks += 1
        prices[:, k + 1] = p
        min_slope = min(min_slope, float(np.min(np.abs(chosen[counts == 1]))))
        edge = min(edge, float(np.min(10 - np.abs(p))))
    assert events_applied == sum((len(v) for v in events.values()))
    return (prices, {'steps': steps, 'paths': n, 'minimum_slope': min_slope, 'minimum_edge_distance': edge, 'maximum_event_mass_error': float(mass_error), 'events_applied': events_applied, 'boundary_fallbacks': fallbacks, 'dx': dx, 'du': du, 'innovation_sigma': sigma})

def _resolution_clock_indices(seed, group, variant, replica, times, candidates=6000):
    from functions.observation import poisson_refresh_path_from_uniforms, mittag_leffler_refresh_path_from_uniforms, tempered_mittag_leffler_refresh_path_from_uniforms, subordinate_two_book_previous_refresh
    dummy = np.zeros((len(times), 2))
    domains = [np.broadcast_to(np.arange(len(times))[:, None], (len(times), 2)).copy()]
    for law in range(1, 4):
        pair = []
        for book in range(2):
            rng = np.random.default_rng(np.random.SeedSequence([seed, group, variant, replica, law, book]))
            u = np.clip(rng.random((4, candidates)), np.nextafter(0.0, 1.0), np.nextafter(1.0, 0.0))
            common = {'horizon': float(times[-1]), 'stream_id': f'v2.2.0-{group}-{variant}-{replica}-{law}-{book}'}
            if law == 1:
                c = poisson_refresh_path_from_uniforms(u[0], 0.1, **common)
            elif law == 2:
                c = mittag_leffler_refresh_path_from_uniforms(u[0], u[1], u[2], beta=0.8, scale_seconds=10.0, **common)
            else:
                c = tempered_mittag_leffler_refresh_path_from_uniforms(u[0], u[1], u[2], u[3], beta=0.8, scale_seconds=10.0, tempering_rate_per_second=0.0125, **common)
            pair.append(c)
        domains.append(subordinate_two_book_previous_refresh(times, dummy, tuple(pair), times).operational_indices)
    return np.array(domains)

def _resolution_impact_batch(start, stop):
    """Independent primitive groups with paired controls and exact symmetry partners."""
    cfg = json.loads(CONFIG_PATH.read_text())["numerical_resolution"]
    dx = cfg["spatial_step"]
    gids = list(range(start, stop)); g = len(gids)
    stride = round((.1 / dx)**2); steps = 1000 * stride; dt = .5 / stride
    lags = np.asarray(cfg["lags_seconds"]); lagsteps = np.rint(lags / dt).astype(int)
    schedules = cfg["event_steps_at_half_second"]
    schedule_steps = [[k * stride for k in ss] for ss in schedules]
    # Injection precedes the update; preserve its physical instant on a finer grid.
    event_steps = [[(k - 1) * stride + 1 for k in ss] for ss in schedules]
    times = dt * np.arange(steps + 1)
    z = []
    for gid in gids:
        raw = np.random.default_rng(np.random.SeedSequence([cfg['path_seed'], gid])).standard_normal((4000, 2))
        if stride == 1:
            raw = raw.reshape(1000, 4, 2).sum(axis=1) / 2
        elif stride == 16:
            bridge = np.random.default_rng(np.random.SeedSequence([cfg['bridge_seed'], gid])).standard_normal((4000, 4, 2))
            bridge = bridge - bridge.mean(axis=1, keepdims=True) + raw[:, None, :] / 2
            raw = bridge.reshape(16000, 2)
        elif stride != 4:
            raise ValueError('Only dx 0.1, 0.05 and 0.025 are supported')
        z.append(raw)
    z = np.array(z)
    expanded = np.broadcast_to(z[:, None], (g, 13, steps, 2)).reshape(-1, steps, 2)
    tapes = []
    for gid in gids:
        for variant in range(1):
            tapes.append([])
            for ss in event_steps:
                for book in range(2):
                    for side in [-1, 1]:
                        tapes.append([OrderEvent(f'v2.2.0-{gid}-{variant}-{book}-{side}-{k}', 'market_order', book, k, side, cfg['child_volume']) for k in ss])
    prices, guard = _resolution_paths(expanded, dx, tapes=tapes)
    base = prices.reshape(g, 13, steps + 1, 2)
    prices = np.empty((g, 4, 13, steps + 1, 2))
    prices[:, 0] = base
    for variant in [1, 2, 3]:
        sign = -1 if variant in [1, 3] else 1
        swap = variant in [2, 3]
        prices[:, variant, 0] = sign * (base[:, 0, :, ::-1] if swap else base[:, 0])
        for scenario in range(3):
            for book in range(2):
                for side in range(2):
                    src = 1 + scenario * 4 + (1 - book if swap else book) * 2 + (1 - side if sign == -1 else side)
                    prices[:, variant, 1 + scenario * 4 + book * 2 + side] = sign * (base[:, src, :, ::-1] if swap else base[:, src])
    directional = np.zeros((g, 4, len(lags), 2, 2))
    means = np.zeros((g, 3, 4, len(lags), 2))
    active = np.zeros_like(means)
    members = np.zeros_like(means)
    build = np.zeros((g, 2, 4, 4, 2))
    build_members = np.zeros_like(build)
    for gi, gid in enumerate(gids):
        for variant in range(4):
            for rep in range(cfg['clock_replicas']):
                indices = _resolution_clock_indices(cfg['clock_seed'], gid, variant, rep, times)
                for scenario, ss in enumerate(schedule_steps):
                    query = ss[-1] + lagsteps
                    for book in range(2):
                        order = [book, 1 - book]
                        for sideidx, side in enumerate([-1, 1]):
                            path = 1 + scenario * 4 + book * 2 + sideidx
                            diff = side * (prices[gi, variant, path] - prices[gi, variant, 0])
                            for domain in range(4):
                                select = indices[domain, query]
                                response = diff[select, np.arange(2)[None, :]][:, order]
                                means[gi, scenario, domain] += response / (16 * cfg['clock_replicas'])
                                if scenario == 0:
                                    directional[gi, domain, :, book, :] += diff[select, np.arange(2)[None, :]] / (8 * cfg['clock_replicas'])
                                active[gi, scenario, domain] += (select >= event_steps[scenario][-1])[:, order] / (16 * cfg['clock_replicas'])
                                if variant == 0 and rep == 0 and (book == 0) and (side == 1):
                                    members[gi, scenario, domain] = response
                                if scenario:
                                    select = indices[domain, ss]
                                    response = diff[select, np.arange(2)[None, :]][:, order]
                                    build[gi, scenario - 1, domain] += response / (16 * cfg['clock_replicas'])
                                    if variant == 0 and rep == 0 and (book == 0) and (side == 1):
                                        build_members[gi, scenario - 1, domain] = response
    return dict(group_ids=np.asarray(gids), lags_seconds=lags, group_mean=means,
                directional_group_mean=directional, primary_individual_response=members,
                final_event_observed_fraction=active, build_up_group_mean=build,
                build_up_primary_response=build_members)

def _resolution_impact_ensemble():
    """Generate the declared groups without external research caches."""
    cfg = json.loads(CONFIG_PATH.read_text())["numerical_resolution"]
    batches = []
    for start in range(0, cfg["independent_groups"], cfg["batch_size"]):
        stop = min(start + cfg["batch_size"], cfg["independent_groups"])
        batches.append(_resolution_impact_batch(start, stop))
        print(f"Impact groups: {stop}/{cfg['independent_groups']}", flush=True)
    return {key: batches[0][key] if key == "lags_seconds" else
            np.concatenate([batch[key] for batch in batches]) for key in batches[0]}

def _plot_numerical_resolution(data=None):
    if data is None:
        with np.load(PROJECT_ROOT / "outputs/impact-ensemble-v2.2.0.npz") as stored:
            data = dict(stored)
    cfg = json.loads((PROJECT_ROOT / "config/config-v1.8.1.json").read_text())["numerical_resolution"]
    assert np.array_equal(data["group_ids"], np.arange(cfg["independent_groups"]))
    x = data["lags_seconds"]
    def save(fig, name):
        stem = PROJECT_ROOT / "figures" / name
        atomic_savefig(fig, Path(str(stem) + ".pdf"), metadata={"CreationDate": None, "ModDate": None})
        if name != "meta-order-individual-envelopes-v2.2.0":
            atomic_savefig(fig, Path(str(stem) + ".png"), dpi=220)
        plt.close(fig)
    def axis_style(ax):
        ax.grid(alpha=.17, linewidth=.5)
    g = data['directional_group_mean']; m = g.mean(0)
    h = cfg['mean_interval_critical_value'] * g.std(0, ddof=1) / np.sqrt(cfg['independent_groups'])
    def style(ax):
        axis_style(ax)
    def interval(ax, x, m, h, c, label, ls='-', lw=1.5):
        ax.fill_between(x, m-h, m+h, color=c, alpha=.12, lw=0)
        ax.plot(x, m, color=c, ls=ls, lw=lw, label=label)
    with plt.rc_context():
        plt.rcdefaults()
        plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": True, "axes.spines.right": True, "pdf.fonttype": 42, "ps.fonttype": 42})
        fig,axes=plt.subplots(2,2,figsize=(10.8,8.2),sharex=True,sharey=True)
        for b in range(2):
         for j in range(2):
          ax=axes[b,j]
          for c,colour,label in [(0,'#2166ac','Operational paired impact'),(1,'#d6604d','Previous-refresh calendar')]:
           interval(ax,x,m[c,:,b,j],h[c,:,b,j],colour,label,lw=1.7)
          ax.axhline(0,color='#777777',lw=.7);style(ax);ax.set_title(f'Event book {b+1} → response book {j+1} ('+('own' if b==j else 'cross')+' impact)',fontsize=10)
          if b==1:ax.set_xlabel('Lag after market event [s]')
          if j==0:ax.set_ylabel('Aggressor-signed log-mid response')
        axes[0,0].legend(frameon=False,fontsize=7.5);fig.suptitle('Paired single-trade own and cross impact');fig.tight_layout(rect=(0,0,1,.96));save(fig,'figure-09-single-trade-impact-v2')


def _resolution_figure7_ensemble(path_count=None):
    """Generate independent-path sufficient statistics for the Figure 7 update."""
    import runpy
    cfg = json.loads((PROJECT_ROOT / "config/config-v1.9.0.json").read_text())["numerical_resolution"]
    clock = runpy.run_path(str(PROJECT_ROOT / "scripts/26_run_clock_only_conformity.py"))
    coupled = runpy.run_path(str(PROJECT_ROOT / "scripts/30_run_combined_no_refit_prediction.py"))
    dynamics = runpy.run_path(str(PROJECT_ROOT / "scripts/33_run_single_trade_impact.py"))
    count = cfg["independent_paths"] if path_count is None else int(path_count)
    batch_size = cfg["batch_size"]
    if count < batch_size or count % batch_size:
        raise ValueError("path count must be a positive multiple of batch size")
    lags = np.asarray(cfg["lags_seconds"], dtype=float)
    step = cfg["step_seconds"]
    lag_steps = np.rint(lags / step).astype(int)
    horizon, warmup = cfg["horizon_seconds"], cfg["warmup_seconds"]
    steps = round((horizon + warmup) / step)
    replicas = cfg["clock_replicas"]
    collections = {"clock": [], "coupled": []}
    for kind in collections:
        for batch, start in enumerate(range(0, count, batch_size)):
            if kind == "clock":
                seed = cfg["clock_batch_seed"] + 10 * batch
                z = np.random.default_rng(seed + 1).standard_normal((batch_size, steps * 4, 2))
                z[:, :, 1] = .8*z[:, :, 0] + .6*z[:, :, 1]
                z = z.reshape(batch_size, steps, 4, 2).sum(2) / 2
                prices, guard = clock["_resolution_paths"](z, .1)
                pairs = clock["_refresh_pairs"](batch_size, replicas, (.1, .1), horizon+warmup, 4096, seed+2, "figure-07")
                times = step * np.arange(prices.shape[1])
                query = warmup + step * np.arange(round(horizon/step)+1)
                indices = np.rint(query/step).astype(int)
                synchronous = clock["_identity_component_groups"](prices, indices, lag_steps)
                asynchronous, reference, _ = clock["_clocked_component_groups"](times, prices, pairs, query, lag_steps)
                values = dict(synchronous=synchronous, asynchronous=asynchronous, reference=reference)
            else:
                z = np.array([np.random.default_rng(np.random.SeedSequence([cfg["coupled_path_seed"], gid])).standard_normal((steps, 2)) for gid in range(start, start+batch_size)])
                prices, guard = dynamics["_resolution_paths"](z)
                pairs = tuple(coupled["_refresh_pairs"](1, replicas, (.1, .1), horizon, 4096, cfg["coupled_clock_seed"]+gid, "figure-07")[0] for gid in range(start, start+batch_size))
                prices = prices[:, round(warmup/step):]
                times = step * np.arange(prices.shape[1])
                query = step * np.arange(round(horizon/step)+1)
                indices = np.rint(query/step).astype(int)
                synchronous = clock["_identity_component_groups"](prices, indices, lag_steps)
                asynchronous, reference, _ = coupled["_clocked_components"](times, prices, pairs, query, lag_steps, .025)
                centre = prices[:, indices].mean(2)
                den = np.array([[sum((path[k:]-path[:-k])**2) for k in lag_steps] for path in centre])
                values = dict(synchronous=synchronous, asynchronous=asynchronous, reference=reference, centre_squares=den)
            collections[kind].append(values)
            print(f"Figure 7 {kind}: {start+batch_size}/{count} paths", flush=True)
    return {kind: {key: np.concatenate([v[key] for v in batches]) for key in batches[0]} for kind, batches in collections.items()}


def main() -> int:
    remove_orphaned_figure_staging_files()
    configuration = _load_configuration()
    policy = configuration["acceptance_policy"]
    output = configuration["output_contract"]
    input_start_hashes = snapshot_hashes(configuration["accepted_inputs"])
    accepted_errors = accepted_input_errors(configuration["accepted_inputs"])
    result = _run_experiment(configuration)
    _plot(result, configuration)

    curve_rows = result["curve_rows"]
    member_rows = result["member_rows"]
    event_rows = result["event_rows"]
    all_filled = all(
        np.isclose(float(row["filled_quantity"]), float(row["quantity"]))
        for row in event_rows
    )
    matrix = configuration["impact_matrix"]
    domains = {row["measurement_domain"] for row in curve_rows}
    input_end_errors = snapshot_errors(input_start_hashes)
    checks = [
        _check("S8I-01", "accepted v1.8.0 input hashes", not accepted_errors, "all accepted hashes exact", not accepted_errors),
        _check("S8I-02", "accepted parent", configuration["accepted_parent"], "equals v1.8.0", configuration["accepted_parent"] == "v1.8.0"),
        _check("S8I-03", "uniform operational dynamics", configuration["architecture"]["operational_dynamics"], "uniform_fixed_grid_only", configuration["architecture"]["operational_dynamics"] == "uniform_fixed_grid_only"),
        _check("S8I-04", "event application timing", configuration["architecture"]["event_application"], "density delta immediately before declared step", configuration["architecture"]["event_application"] == "market_order_density_delta_immediately_before_declared_operational_step"),
        _check("S8I-05", "paired-control construction", configuration["architecture"]["paired_control"], "common initial state and innovations", configuration["architecture"]["paired_control"] == "identical_initial_state_and_common_operational_innovations"),
        _check("S8I-06", "operational impact estimand", configuration["architecture"]["operational_measurement"], "aggressor-signed shocked minus control", configuration["architecture"]["operational_measurement"] == "aggressor_signed_shocked_minus_control_boundary_price"),
        _check("S8I-07", "calendar impact estimand", configuration["architecture"]["calendar_measurement"], "same paired paths after subordination", configuration["architecture"]["calendar_measurement"] == "aggressor_signed_subordinated_shocked_minus_control_boundary_price"),
        _check("S8I-08", "calendar interpolation", configuration["architecture"]["calendar_interpolation"], "forbidden", configuration["architecture"]["calendar_interpolation"] == "forbidden"),
        _check("S8I-09", "legacy nonuniform update", configuration["architecture"]["legacy_nonuniform_state_update"], "forbidden", configuration["architecture"]["legacy_nonuniform_state_update"] == "forbidden"),
        _check("S8I-10", "source-v1 change", configuration["architecture"]["source_v1_change"], "false", configuration["architecture"]["source_v1_change"] is False),
        _check("S8I-11", "declared path count", result["base_inputs"].shape[0], f"equals {configuration['experiment']['paths']}", result["base_inputs"].shape[0] == int(configuration["experiment"]["paths"])),
        _check("S8I-12", "microscopic input correlation", result["input_correlation"], f"absolute <= {policy['maximum_input_correlation_absolute']}", abs(result["input_correlation"]) <= float(policy["maximum_input_correlation_absolute"])),
        _check("S8I-13", "symmetry-controlled input mean", np.mean(result["base_inputs"], axis=(0, 1)), "both zero within 1e-14", bool(np.all(np.abs(np.mean(result["base_inputs"], axis=(0, 1))) <= 1e-14))),
        _check("S8I-14", "book input variances", np.var(result["base_inputs"], axis=(0, 1)), "equal within 1e-14", bool(np.isclose(np.var(result["base_inputs"][:, :, 0]), np.var(result["base_inputs"][:, :, 1]), atol=1e-14, rtol=0.0))),
        _check("S8I-15", "all market events fully filled", all_filled, "true", all_filled),
        _check("S8I-16", "event density-mass conservation", result["event_mass_error"], "maximum absolute error <= 1e-14", result["event_mass_error"] <= 1e-14),
        _check("S8I-17", "execution proxy lies on aggressor side", result["minimum_execution_side_product"], "strictly positive", result["minimum_execution_side_product"] > 0.0),
        _check("S8I-18", "ground-truth event signs", {int(row["ground_truth_aggressor_sign"]) for row in event_rows}, "equals {-1,+1}", {int(row["ground_truth_aggressor_sign"]) for row in event_rows} == {-1, 1}),
        _check("S8I-19", "quote-midpoint signs", all(int(row["quote_midpoint_sign"]) == int(row["side"]) for row in event_rows), "all equal event side", all(int(row["quote_midpoint_sign"]) == int(row["side"]) for row in event_rows)),
        _check("S8I-20", "pre-event shocked/control identity", result["pre_event_maximum"], f"maximum <= {policy['maximum_pre_event_absolute_paired_difference']}", result["pre_event_maximum"] <= float(policy["maximum_pre_event_absolute_paired_difference"])),
        _check("S8I-21", "unique reaction boundaries", result["maximum_candidates"], f"equals {policy['required_boundary_candidates']}", result["maximum_candidates"] == int(policy["required_boundary_candidates"])),
        _check("S8I-22", "interior reaction boundaries", result["minimum_edge"], f"minimum >= {policy['minimum_boundary_edge_distance']}", result["minimum_edge"] >= float(policy["minimum_boundary_edge_distance"])),
        _check("S8I-23", "operational own impact at event state", result["operational_own_zero"], f">= {policy['minimum_operational_own_impact_at_zero_lag']}", result["operational_own_zero"] >= float(policy["minimum_operational_own_impact_at_zero_lag"])),
        _check("S8I-24", "simultaneous cross impact at event state", result["operational_cross_zero"], "absolute <= 1e-12", result["operational_cross_zero"] <= 1e-12),
        _check("S8I-25", "operational cross impact at 20 seconds", result["operational_cross_twenty"], f">= {policy['minimum_operational_cross_impact_at_20_seconds']}", result["operational_cross_twenty"] >= float(policy["minimum_operational_cross_impact_at_20_seconds"])),
        _check("S8I-26", "book-exchange symmetry", result["book_difference"], f"maximum relative difference <= {policy['maximum_book_exchange_relative_difference']}", result["book_difference"] <= float(policy["maximum_book_exchange_relative_difference"])),
        _check("S8I-27", "buy/sell symmetry on domain own-impact scale", result["side_difference"], f"maximum domain-scaled difference <= {policy['maximum_buy_sell_domain_scaled_difference']}", result["side_difference"] <= float(policy["maximum_buy_sell_domain_scaled_difference"])),
        _check("S8I-28", "long-lag own/cross convergence ratio", result["long_ratio"], f"in [{policy['minimum_long_lag_own_cross_ratio']}, {policy['maximum_long_lag_own_cross_ratio']}]", float(policy["minimum_long_lag_own_cross_ratio"]) <= result["long_ratio"] <= float(policy["maximum_long_lag_own_cross_ratio"])),
        _check("S8I-29", "book-specific clock paths are distinct", result["distinct_clock_pairs"], "true for every path", result["distinct_clock_pairs"]),
        _check("S8I-30", "realised refresh rates", result["clock_relative_error"], "maximum relative error <= 0.35", result["clock_relative_error"] <= 0.35),
        _check("S8I-31", "calendar activity at event time", result["calendar_active_zero"], f"<= {policy['maximum_calendar_active_fraction_at_zero_lag']}", result["calendar_active_zero"] <= float(policy["maximum_calendar_active_fraction_at_zero_lag"])),
        _check("S8I-32", "calendar activity by 40 seconds", result["calendar_active_forty"], f">= {policy['minimum_calendar_active_fraction_at_40_seconds']}", result["calendar_active_forty"] >= float(policy["minimum_calendar_active_fraction_at_40_seconds"])),
        _check("S8I-33", "calendar own impact by 40 seconds", result["calendar_own_forty"], f">= {policy['minimum_calendar_own_impact_at_40_seconds']}", result["calendar_own_forty"] >= float(policy["minimum_calendar_own_impact_at_40_seconds"])),
        _check("S8I-34", "measurement domains", domains, "operational and calendar", domains == {"operational", "calendar"}),
        _check("S8I-35", "complete two-book impact matrix", {(row["event_book"], row["response_book"]) for row in matrix}, "four cells", {(row["event_book"], row["response_book"]) for row in matrix} == {(0, 0), (0, 1), (1, 0), (1, 1)}),
        _check("S8I-36", "curve output rows", len(curve_rows), f"equals {output['curve_rows']}", len(curve_rows) == int(output["curve_rows"])),
        _check("S8I-37", "member output rows", len(member_rows), f"equals {output['member_rows']}", len(member_rows) == int(output["member_rows"])),
        _check("S8I-38", "event output rows", len(event_rows), f"equals {output['event_rows']}", len(event_rows) == int(output["event_rows"])),
        _check("S8I-39", "path archive", PATH_ARCHIVE.is_file() and PATH_ARCHIVE.stat().st_size > 0, "nonempty NPZ", PATH_ARCHIVE.is_file() and PATH_ARCHIVE.stat().st_size > 0),
        _check("S8I-40", "Figure 9 pair", all(FIGURE_STEM.with_suffix(suffix).is_file() for suffix in (".pdf", ".png")), "PDF and PNG", all(FIGURE_STEM.with_suffix(suffix).is_file() for suffix in (".pdf", ".png"))),
        _check("S8I-41", "accepted inputs unchanged", not input_end_errors, "all start/end hashes exact", not input_end_errors),
        _check("S8I-42", "no new theoretical impact curve", output["new_theoretical_impact_curve"], "false", output["new_theoretical_impact_curve"] is False),
        _check("S8I-43", "meta-order and dependence boundary", [configuration["stage_boundary"]["meta_order_not_implemented"], configuration["stage_boundary"]["dependence_diagnostics_not_implemented"]], "both true", configuration["stage_boundary"]["meta_order_not_implemented"] is True and configuration["stage_boundary"]["dependence_diagnostics_not_implemented"] is True),
        _check("S8I-44", "next numeric gate", configuration["stage_boundary"]["next_stage_on_acceptance"], "v1.8.2 meta-order impact", configuration["stage_boundary"]["next_stage_on_acceptance"] == "v1.8.2_meta_order_own_and_cross_impact"),
    ]
    failed = sum(row["status"] == "Failed" for row in checks)
    summary = {
        "target_id": configuration["target_id"],
        "result_label": output["result_label_when_checks_pass"] if failed == 0 else "failed",
        "paths": configuration["experiment"]["paths"],
        "event_scenarios": len(event_rows),
        "curve_rows": len(curve_rows),
        "member_rows": len(member_rows),
        "operational_own_impact_at_zero_seconds": result["operational_own_zero"],
        "operational_cross_impact_at_twenty_seconds": result["operational_cross_twenty"],
        "calendar_own_impact_at_forty_seconds": result["calendar_own_forty"],
        "long_lag_operational_own_cross_ratio": result["long_ratio"],
        "buy_sell_domain_scaled_difference": result["side_difference"],
        "buy_sell_cellwise_relative_diagnostic": result["side_local_relative_difference"],
        "verified_checks": len(checks) - failed,
        "failed_checks": failed,
        "next_stage": output["next_stage"],
        "software_version": VERSION,
    }
    write_csv(SUMMARY_PATH, list(summary), [summary])
    write_csv(CHECK_PATH, list(checks[0]), checks)
    for row in checks:
        print(f"{row['check_id']}: {row['status']} - {row['check']}")
    print(
        f"Single-trade impact route completed: {len(checks) - failed} checks verified, "
        f"{failed} failures; {len(curve_rows)} curve rows and {len(member_rows)} member rows."
    )
    print("Figure 9 generated with operational and explicitly subordinated impact on one common linear scale.")
    if failed:
        return 1
    if "numerical_resolution" in configuration:
        data = _resolution_impact_ensemble()
        target = PROJECT_ROOT / "outputs/impact-ensemble-v2.2.0.npz"
        temporary = target.with_suffix(".tmp.npz")
        np.savez_compressed(temporary, **data)
        temporary.replace(target)
        _plot_numerical_resolution(data)
        ensembles = _resolution_figure7_ensemble()
        target = PROJECT_ROOT / "outputs/figure-07-ensemble-v2.2.0.npz"
        temporary = target.with_suffix(".tmp.npz")
        np.savez_compressed(temporary, **{kind + "__" + key: value
                            for kind, group in ensembles.items() for key, value in group.items()})
        temporary.replace(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
