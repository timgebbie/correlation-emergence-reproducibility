"""Run the v1.8.2 scheduled meta-order own/cross-impact experiment."""

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

from functions.events import MetaOrderSchedule, operational_translation_meta_order_pair
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


VERSION = "1.8.2"
CONFIG_PATH = PROJECT_ROOT / "config" / "config-v1.8.2.json"
CHECK_PATH = PROJECT_ROOT / "diagnostics" / "meta-order-impact-checks-v1.8.csv"
TRAJECTORY_CURVE_PATH = PROJECT_ROOT / "outputs" / "meta-order-impact-trajectory-v1.8.csv"
TRAJECTORY_MEMBER_PATH = PROJECT_ROOT / "outputs" / "meta-order-impact-trajectory-members-v1.8.csv"
RELAXATION_CURVE_PATH = PROJECT_ROOT / "outputs" / "meta-order-impact-relaxation-v1.8.csv"
RELAXATION_MEMBER_PATH = PROJECT_ROOT / "outputs" / "meta-order-impact-relaxation-members-v1.8.csv"
EVENT_PATH = PROJECT_ROOT / "outputs" / "meta-order-impact-events-v1.8.csv"
SCHEDULE_PATH = PROJECT_ROOT / "outputs" / "meta-order-impact-schedules-v1.8.csv"
CLOCK_PATH = PROJECT_ROOT / "outputs" / "meta-order-impact-clock-rates-v1.8.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "meta-order-impact-summary-v1.8.csv"
PATH_ARCHIVE = PROJECT_ROOT / "outputs" / "meta-order-impact-paths-v1.8.npz"
FIGURE_STEM = PROJECT_ROOT / "figures" / "figure-10-meta-order-impact-v2"


def _load_configuration() -> dict[str, object]:
    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if configuration.get("schema_version") != VERSION:
        raise ValueError("meta-order impact configuration version mismatch")
    if configuration["architecture"]["operational_dynamics"] != "uniform_fixed_grid_only":
        raise ValueError("v1.8.2 requires uniform operational dynamics")
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
                    stream_id=f"v1.8.2-path-{path:02d}-book-{book + 1}",
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


def _side_difference(trajectory: np.ndarray, relaxation: np.ndarray) -> tuple[float, float]:
    trajectory_side = np.mean(trajectory, axis=1)
    relaxation_side = np.mean(relaxation, axis=1)
    local_scale = np.maximum(
        np.maximum(np.abs(trajectory_side[:, :, 0]), np.abs(trajectory_side[:, :, 1])),
        1e-8,
    )
    local_supported = local_scale > 1e-6
    local_trajectory = float(
        np.max(
            np.abs(trajectory_side[:, :, 0] - trajectory_side[:, :, 1])[local_supported]
            / local_scale[local_supported]
        )
    )
    local_scale_relax = np.maximum(
        np.maximum(np.abs(relaxation_side[:, :, 0]), np.abs(relaxation_side[:, :, 1])),
        1e-8,
    )
    local_supported_relax = local_scale_relax > 1e-6
    local_relaxation = float(
        np.max(
            np.abs(relaxation_side[:, :, 0] - relaxation_side[:, :, 1])[
                local_supported_relax
            ]
            / local_scale_relax[local_supported_relax]
        )
    )

    ratios = []
    for domain in range(2):
        maximum_difference = max(
            float(
                np.max(
                    np.abs(
                        trajectory_side[:, :, 0, domain]
                        - trajectory_side[:, :, 1, domain]
                    )
                )
            ),
            float(
                np.max(
                    np.abs(
                        relaxation_side[:, :, 0, domain]
                        - relaxation_side[:, :, 1, domain]
                    )
                )
            ),
        )
        own_scale = 0.0
        for schedule in range(trajectory_side.shape[0]):
            for book in range(2):
                own_scale = max(
                    own_scale,
                    float(
                        np.max(
                            0.5
                            * (
                                np.abs(trajectory_side[schedule, book, 0, domain, :, book])
                                + np.abs(trajectory_side[schedule, book, 1, domain, :, book])
                            )
                        )
                    ),
                    float(
                        np.max(
                            0.5
                            * (
                                np.abs(relaxation_side[schedule, book, 0, domain, :, book])
                                + np.abs(relaxation_side[schedule, book, 1, domain, :, book])
                            )
                        )
                    ),
                )
        if own_scale <= 0.0:
            raise ValueError("buy/sell normalization requires positive own impact")
        ratios.append(maximum_difference / own_scale)
    return max(ratios), max(local_trajectory, local_relaxation)


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
    schedule_specs = tuple(experiment["schedules"])
    schedule_count = len(schedule_specs)
    paths = int(experiment["paths"])
    steps = int(experiment["total_operational_steps"])
    event_books = tuple(int(value) for value in experiment["event_books"])
    sides = tuple(int(value) for value in experiment["event_sides"])
    child_quantity = float(experiment["child_quantity"])
    child_count = int(experiment["children_per_meta_order"])
    post_lags = np.asarray(experiment["post_completion_lags_seconds"], dtype=float)
    step_seconds = float(model["operational_step_seconds"])
    post_lag_steps = np.rint(post_lags / step_seconds).astype(int)
    if np.any(np.abs(post_lag_steps * step_seconds - post_lags) > 1e-12):
        raise ValueError("post-completion lags must lie on the operational grid")
    for spec in schedule_specs:
        declared_steps = np.asarray(spec["child_operational_steps"], dtype=int)
        if declared_steps.size != child_count:
            raise ValueError("schedule child count does not match the declaration")
        if declared_steps[-1] + int(np.max(post_lag_steps)) > steps:
            raise ValueError("post-completion lags exceed the path")

    grid, diffusion, sources, stationary, kernels, solver, couplings, innovation_policy = _model(configuration)
    base_inputs = _symmetry_controlled_inputs(configuration)
    operational_times_seconds = np.arange(steps + 1, dtype=float) * step_seconds
    refresh_pairs = _refresh_pairs(configuration, float(operational_times_seconds[-1]))

    trajectory = np.empty(
        (schedule_count, paths, 2, 2, 2, child_count, 2), dtype=float
    )
    trajectory_active = np.ones_like(trajectory)
    relaxation = np.empty(
        (schedule_count, paths, 2, 2, 2, post_lags.size, 2), dtype=float
    )
    relaxation_active = np.ones_like(relaxation)
    control_prices = np.empty((paths, steps + 1, 2), dtype=float)
    shocked_prices = np.empty((schedule_count, paths, 2, 2, steps + 1, 2), dtype=float)
    calendar_control = np.empty_like(control_prices)
    calendar_shocked = np.empty_like(shocked_prices)
    calendar_indices = np.empty((paths, steps + 1, 2), dtype=np.int64)
    event_rows: list[dict[str, object]] = []
    schedule_rows: list[dict[str, object]] = []
    clock_rows: list[dict[str, object]] = []
    pre_event_maximum = 0.0
    minimum_edge = math.inf
    maximum_candidates = 0
    event_mass_errors: list[float] = []
    execution_side_products: list[float] = []

    for spec in schedule_specs:
        schedule_rows.append(
            {
                "schedule_id": spec["schedule_id"],
                "child_count": child_count,
                "child_quantity": child_quantity,
                "total_quantity": child_count * child_quantity,
                "child_operational_steps": json.dumps(spec["child_operational_steps"]),
                "child_times_from_start_seconds": json.dumps(spec["child_times_from_start_seconds"]),
                "execution_horizon_seconds": spec["execution_horizon_seconds"],
                "signed_execution_rate_proxy_per_second": spec["signed_execution_rate_proxy_per_second"],
                "participation_rate_status": experiment["participation_rate_status"],
                "software_version": VERSION,
            }
        )

    for path_index in range(paths):
        control_written = False
        sampled_control_written = False
        for schedule_index, spec in enumerate(schedule_specs):
            child_steps = tuple(int(value) for value in spec["child_operational_steps"])
            for event_book in event_books:
                for side_index, side in enumerate(sides):
                    meta_order_id = (
                        f"v182-{spec['schedule_id']}-p{path_index:02d}-"
                        f"b{event_book + 1}-s{side:+d}"
                    )
                    schedule = MetaOrderSchedule(
                        meta_order_id=meta_order_id,
                        book_index=event_book,
                        side=side,
                        child_operational_steps=child_steps,
                        child_quantities=(child_quantity,) * child_count,
                    )
                    pair = operational_translation_meta_order_pair(
                        grid,
                        stationary,
                        (0.0, 0.0),
                        sources,
                        couplings,
                        kernels,
                        base_inputs[path_index],
                        innovation_policy,
                        diffusion,
                        solver,
                        schedule,
                    )
                    if not control_written:
                        control_prices[path_index] = pair.control_prices
                        control_written = True
                    elif not np.array_equal(control_prices[path_index], pair.control_prices):
                        raise RuntimeError("control path changed across meta-order scenarios")
                    shocked_prices[schedule_index, path_index, event_book, side_index] = pair.shocked_prices
                    pre_event_maximum = max(
                        pre_event_maximum,
                        float(np.max(np.abs(pair.paired_price_difference[: schedule.first_step]))),
                    )
                    minimum_edge = min(
                        minimum_edge,
                        float(np.min(pair.shocked_boundary_edge_distances)),
                    )
                    maximum_candidates = max(
                        maximum_candidates,
                        int(np.max(pair.shocked_boundary_candidate_counts)),
                    )
                    for application in pair.event_applications:
                        applied_mass = float(
                            (grid[1] - grid[0]) * np.sum(np.abs(application.density_delta))
                        )
                        event_mass_errors.append(abs(applied_mass - application.event.quantity))
                        execution_side_products.append(
                            application.event.side
                            * (
                                float(application.execution_log_price)
                                - application.pre_event_mid_log_price
                            )
                        )
                        event_rows.append(
                            {
                                "meta_order_id": application.event.meta_order_id,
                                "schedule_id": spec["schedule_id"],
                                "path_index": path_index,
                                "event_book": event_book,
                                "side": side,
                                "child_index": application.event.child_index,
                                "operational_step": application.event.operational_step,
                                "operational_time_seconds": operational_times_seconds[
                                    application.event.operational_step
                                ],
                                "quantity": application.event.quantity,
                                "cumulative_quantity": child_quantity
                                * (int(application.event.child_index) + 1),
                                "filled_quantity": application.filled_quantity,
                                "pre_event_mid_log_price": application.pre_event_mid_log_price,
                                "execution_log_price_proxy": application.execution_log_price,
                                "affected_grid_indices": json.dumps(
                                    application.affected_grid_indices
                                ),
                                "applied_density_mass": applied_mass,
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
                        raise RuntimeError("calendar control changed across meta-order scenarios")
                    calendar_shocked[
                        schedule_index, path_index, event_book, side_index
                    ] = sampled_shocked.prices

                    child_indices = np.asarray(child_steps, dtype=int)
                    operational_signed = pair.signed_price_response[child_indices]
                    calendar_signed = side * (
                        sampled_shocked.prices[child_indices]
                        - sampled_control.prices[child_indices]
                    )
                    trajectory[schedule_index, path_index, event_book, side_index, 0] = operational_signed
                    trajectory[schedule_index, path_index, event_book, side_index, 1] = calendar_signed
                    trajectory_active[
                        schedule_index, path_index, event_book, side_index, 1
                    ] = (
                        sampled_control.operational_indices[child_indices]
                        >= child_indices[:, None]
                    ).astype(float)

                    relaxation_indices = schedule.last_step + post_lag_steps
                    operational_relaxation = pair.signed_price_response[relaxation_indices]
                    calendar_relaxation = side * (
                        sampled_shocked.prices[relaxation_indices]
                        - sampled_control.prices[relaxation_indices]
                    )
                    relaxation[schedule_index, path_index, event_book, side_index, 0] = operational_relaxation
                    relaxation[schedule_index, path_index, event_book, side_index, 1] = calendar_relaxation
                    relaxation_active[
                        schedule_index, path_index, event_book, side_index, 1
                    ] = (
                        sampled_control.operational_indices[relaxation_indices]
                        >= schedule.last_step
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
            print(f"  completed meta-order path {path_index + 1}/{paths}")

    trajectory_rows: list[dict[str, object]] = []
    trajectory_member_rows: list[dict[str, object]] = []
    trajectory_mean = np.empty((schedule_count, 2, 2, 2, child_count), dtype=float)
    trajectory_se = np.empty_like(trajectory_mean)
    trajectory_support = np.empty_like(trajectory_mean)
    for schedule_index, spec in enumerate(schedule_specs):
        cumulative = np.arange(1, child_count + 1, dtype=float) * child_quantity
        elapsed = np.asarray(spec["child_times_from_start_seconds"], dtype=float)
        for event_book in event_books:
            for response_book in range(2):
                impact_type = "own" if event_book == response_book else "cross"
                for domain_index, domain in enumerate(("operational", "calendar")):
                    values = trajectory[
                        schedule_index, :, event_book, :, domain_index, :, response_book
                    ]
                    path_side_means = np.mean(values, axis=1)
                    means = np.mean(path_side_means, axis=0)
                    errors = np.std(path_side_means, axis=0, ddof=1) / np.sqrt(paths)
                    support = np.mean(
                        trajectory_active[
                            schedule_index,
                            :,
                            event_book,
                            :,
                            domain_index,
                            :,
                            response_book,
                        ],
                        axis=(0, 1),
                    )
                    trajectory_mean[
                        schedule_index, event_book, response_book, domain_index
                    ] = means
                    trajectory_se[
                        schedule_index, event_book, response_book, domain_index
                    ] = errors
                    trajectory_support[
                        schedule_index, event_book, response_book, domain_index
                    ] = support
                    for child_index in range(child_count):
                        trajectory_rows.append(
                            {
                                "target_id": configuration["target_id"],
                                "schedule_id": spec["schedule_id"],
                                "execution_horizon_seconds": spec["execution_horizon_seconds"],
                                "measurement_domain": domain,
                                "event_book": event_book,
                                "response_book": response_book,
                                "impact_type": impact_type,
                                "child_index": child_index,
                                "elapsed_from_start_seconds": elapsed[child_index],
                                "scheduled_cumulative_quantity": cumulative[child_index],
                                "mean_signed_log_mid_impact": means[child_index],
                                "standard_error": errors[child_index],
                                "normal_95_lower": means[child_index] - 1.96 * errors[child_index],
                                "normal_95_upper": means[child_index] + 1.96 * errors[child_index],
                                "active_observation_fraction": support[child_index],
                                "paths": paths,
                                "sides_per_path": len(sides),
                                "software_version": VERSION,
                            }
                        )
                    for path_index in range(paths):
                        for side_index, side in enumerate(sides):
                            for child_index in range(child_count):
                                value = values[path_index, side_index, child_index]
                                trajectory_member_rows.append(
                                    {
                                        "schedule_id": spec["schedule_id"],
                                        "path_index": path_index,
                                        "measurement_domain": domain,
                                        "event_book": event_book,
                                        "response_book": response_book,
                                        "impact_type": impact_type,
                                        "event_side": side,
                                        "child_index": child_index,
                                        "elapsed_from_start_seconds": elapsed[child_index],
                                        "scheduled_cumulative_quantity": cumulative[child_index],
                                        "signed_log_mid_impact": value,
                                        "active_observation": trajectory_active[
                                            schedule_index,
                                            path_index,
                                            event_book,
                                            side_index,
                                            domain_index,
                                            child_index,
                                            response_book,
                                        ],
                                        "software_version": VERSION,
                                    }
                                )

    relaxation_rows: list[dict[str, object]] = []
    relaxation_member_rows: list[dict[str, object]] = []
    relaxation_mean = np.empty((schedule_count, 2, 2, 2, post_lags.size), dtype=float)
    relaxation_se = np.empty_like(relaxation_mean)
    relaxation_support = np.empty_like(relaxation_mean)
    for schedule_index, spec in enumerate(schedule_specs):
        for event_book in event_books:
            for response_book in range(2):
                impact_type = "own" if event_book == response_book else "cross"
                for domain_index, domain in enumerate(("operational", "calendar")):
                    values = relaxation[
                        schedule_index, :, event_book, :, domain_index, :, response_book
                    ]
                    path_side_means = np.mean(values, axis=1)
                    means = np.mean(path_side_means, axis=0)
                    errors = np.std(path_side_means, axis=0, ddof=1) / np.sqrt(paths)
                    support = np.mean(
                        relaxation_active[
                            schedule_index,
                            :,
                            event_book,
                            :,
                            domain_index,
                            :,
                            response_book,
                        ],
                        axis=(0, 1),
                    )
                    relaxation_mean[
                        schedule_index, event_book, response_book, domain_index
                    ] = means
                    relaxation_se[
                        schedule_index, event_book, response_book, domain_index
                    ] = errors
                    relaxation_support[
                        schedule_index, event_book, response_book, domain_index
                    ] = support
                    for lag_index, lag in enumerate(post_lags):
                        relaxation_rows.append(
                            {
                                "target_id": configuration["target_id"],
                                "schedule_id": spec["schedule_id"],
                                "execution_horizon_seconds": spec["execution_horizon_seconds"],
                                "measurement_domain": domain,
                                "event_book": event_book,
                                "response_book": response_book,
                                "impact_type": impact_type,
                                "post_completion_lag_seconds": lag,
                                "mean_signed_log_mid_impact": means[lag_index],
                                "standard_error": errors[lag_index],
                                "normal_95_lower": means[lag_index] - 1.96 * errors[lag_index],
                                "normal_95_upper": means[lag_index] + 1.96 * errors[lag_index],
                                "active_observation_fraction": support[lag_index],
                                "paths": paths,
                                "sides_per_path": len(sides),
                                "software_version": VERSION,
                            }
                        )
                    for path_index in range(paths):
                        for side_index, side in enumerate(sides):
                            for lag_index, lag in enumerate(post_lags):
                                value = values[path_index, side_index, lag_index]
                                relaxation_member_rows.append(
                                    {
                                        "schedule_id": spec["schedule_id"],
                                        "path_index": path_index,
                                        "measurement_domain": domain,
                                        "event_book": event_book,
                                        "response_book": response_book,
                                        "impact_type": impact_type,
                                        "event_side": side,
                                        "post_completion_lag_seconds": lag,
                                        "signed_log_mid_impact": value,
                                        "active_observation": relaxation_active[
                                            schedule_index,
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

    side_difference, side_local = _side_difference(trajectory, relaxation)
    book_difference = 0.0
    for schedule in range(schedule_count):
        for domain in range(2):
            book_difference = max(
                book_difference,
                _relative_difference(
                    trajectory_mean[schedule, 0, 0, domain],
                    trajectory_mean[schedule, 1, 1, domain],
                ),
                _relative_difference(
                    trajectory_mean[schedule, 0, 1, domain],
                    trajectory_mean[schedule, 1, 0, domain],
                ),
                _relative_difference(
                    relaxation_mean[schedule, 0, 0, domain],
                    relaxation_mean[schedule, 1, 1, domain],
                ),
                _relative_difference(
                    relaxation_mean[schedule, 0, 1, domain],
                    relaxation_mean[schedule, 1, 0, domain],
                ),
            )

    own_trajectory = np.asarray(
        [
            np.mean(
                [
                    trajectory_mean[schedule, 0, 0, 0],
                    trajectory_mean[schedule, 1, 1, 0],
                ],
                axis=0,
            )
            for schedule in range(schedule_count)
        ]
    )
    cross_trajectory = np.asarray(
        [
            np.mean(
                [
                    trajectory_mean[schedule, 0, 1, 0],
                    trajectory_mean[schedule, 1, 0, 0],
                ],
                axis=0,
            )
            for schedule in range(schedule_count)
        ]
    )
    own_relaxation = np.asarray(
        [
            np.mean(
                [
                    relaxation_mean[schedule, 0, 0, 0],
                    relaxation_mean[schedule, 1, 1, 0],
                ],
                axis=0,
            )
            for schedule in range(schedule_count)
        ]
    )
    cross_relaxation = np.asarray(
        [
            np.mean(
                [
                    relaxation_mean[schedule, 0, 1, 0],
                    relaxation_mean[schedule, 1, 0, 0],
                ],
                axis=0,
            )
            for schedule in range(schedule_count)
        ]
    )
    own_increments = np.diff(own_trajectory, axis=1)
    horizon_difference = float(abs(own_trajectory[0, -1] - own_trajectory[1, -1]))
    own_relaxation_fractions = (
        own_relaxation[:, 0] - own_relaxation[:, -1]
    ) / np.maximum(np.abs(own_relaxation[:, 0]), 1e-8)
    # Cross-impact can first catch up and then relax with own-impact.  Measuring
    # catch-up only at the final lag confounds those two phases, especially for
    # the slower schedule where coupling already acts between child events.
    # The long-lag own/cross ratio below separately tests convergence.
    cross_relaxation_peaks = np.max(cross_relaxation, axis=1)
    cross_catchup_fractions = (
        cross_relaxation_peaks - cross_relaxation[:, 0]
    ) / np.maximum(np.abs(cross_relaxation_peaks), 1e-8)
    long_ratios = own_relaxation[:, -1] / cross_relaxation[:, -1]
    lag_eighty = int(np.flatnonzero(np.isclose(post_lags, 80.0))[0])
    calendar_active_eighty = float(np.min(relaxation_support[:, :, :, 1, lag_eighty]))
    calendar_own_eighty = float(
        np.min(
            [
                np.mean(
                    [
                        relaxation_mean[schedule, 0, 0, 1, lag_eighty],
                        relaxation_mean[schedule, 1, 1, 1, lag_eighty],
                    ]
                )
                for schedule in range(schedule_count)
            ]
        )
    )

    input_flat = base_inputs.reshape(-1, 2)
    input_correlation = float(np.corrcoef(input_flat.T)[0, 1])
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
        write_csv(TRAJECTORY_CURVE_PATH, list(trajectory_rows[0]), trajectory_rows)
        write_csv(TRAJECTORY_MEMBER_PATH, list(trajectory_member_rows[0]), trajectory_member_rows)
        write_csv(RELAXATION_CURVE_PATH, list(relaxation_rows[0]), relaxation_rows)
        write_csv(RELAXATION_MEMBER_PATH, list(relaxation_member_rows[0]), relaxation_member_rows)
        write_csv(EVENT_PATH, list(event_rows[0]), event_rows)
        write_csv(SCHEDULE_PATH, list(schedule_rows[0]), schedule_rows)
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
            trajectory_responses=trajectory,
            trajectory_active=trajectory_active,
            relaxation_responses=relaxation,
            relaxation_active=relaxation_active,
            post_completion_lags_seconds=post_lags,
            post_completion_lag_steps=post_lag_steps,
        )
    return {
        "base_inputs": base_inputs,
        "trajectory": trajectory,
        "trajectory_active": trajectory_active,
        "relaxation": relaxation,
        "relaxation_active": relaxation_active,
        "trajectory_rows": trajectory_rows,
        "trajectory_member_rows": trajectory_member_rows,
        "relaxation_rows": relaxation_rows,
        "relaxation_member_rows": relaxation_member_rows,
        "event_rows": event_rows,
        "schedule_rows": schedule_rows,
        "clock_rows": clock_rows,
        "trajectory_mean": trajectory_mean,
        "trajectory_se": trajectory_se,
        "trajectory_support": trajectory_support,
        "relaxation_mean": relaxation_mean,
        "relaxation_se": relaxation_se,
        "relaxation_support": relaxation_support,
        "post_lags": post_lags,
        "input_correlation": input_correlation,
        "pre_event_maximum": pre_event_maximum,
        "minimum_edge": minimum_edge,
        "maximum_candidates": maximum_candidates,
        "event_mass_error": max(event_mass_errors),
        "minimum_execution_side_product": min(execution_side_products),
        "side_difference": side_difference,
        "side_local_relative_difference": side_local,
        "book_difference": book_difference,
        "own_trajectory": own_trajectory,
        "cross_trajectory": cross_trajectory,
        "minimum_own_increment": float(np.min(own_increments)),
        "horizon_difference": horizon_difference,
        "own_relaxation_fractions": own_relaxation_fractions,
        "cross_catchup_fractions": cross_catchup_fractions,
        "long_ratios": long_ratios,
        "calendar_active_eighty": calendar_active_eighty,
        "calendar_own_eighty": calendar_own_eighty,
        "clock_relative_error": clock_relative_error,
        "distinct_clock_pairs": distinct_clock_pairs,
        "operational_times_seconds": operational_times_seconds,
        "control_prices": control_prices,
        "shocked_prices": shocked_prices,
        "calendar_control": calendar_control,
        "calendar_shocked": calendar_shocked,
        "calendar_indices": calendar_indices,
    }


def _figure_members(values: np.ndarray, impact_type: str) -> np.ndarray:
    if impact_type == "own":
        first = values[:, :, 0, :, :, :, 0]
        second = values[:, :, 1, :, :, :, 1]
    else:
        first = values[:, :, 0, :, :, :, 1]
        second = values[:, :, 1, :, :, :, 0]
    return np.mean(np.mean(np.stack((first, second), axis=0), axis=0), axis=2)


def _plot(result: dict[str, object], configuration: dict[str, object]) -> None:
    experiment = configuration["experiment"]
    schedule_specs = experiment["schedules"]
    cumulative = np.arange(1, int(experiment["children_per_meta_order"]) + 1) * float(
        experiment["child_quantity"]
    )
    post_lags = result["post_lags"]
    figure, axes = plt.subplots(2, 2, figsize=(10.8, 8.2), sharey=True)
    colors = ("#2166ac", "#b35806")
    linestyles = ("-", "--")
    domain_labels = ("Operational", "Previous-refresh calendar")
    plotted: list[tuple[np.ndarray, np.ndarray]] = []

    for column, impact_type in enumerate(("own", "cross")):
        trajectory_members = _figure_members(result["trajectory"], impact_type)
        relaxation_members = _figure_members(result["relaxation"], impact_type)
        for schedule_index, spec in enumerate(schedule_specs):
            for domain in range(2):
                for row_index, (x_values, members) in enumerate(
                    (
                        (cumulative, trajectory_members[schedule_index, :, domain]),
                        (post_lags, relaxation_members[schedule_index, :, domain]),
                    )
                ):
                    mean = np.mean(members, axis=0)
                    error = np.std(members, axis=0, ddof=1) / np.sqrt(members.shape[0])
                    plotted.append((mean - 1.96 * error, mean + 1.96 * error))
                    label = (
                        f"{spec['schedule_id'].capitalize()} {int(spec['execution_horizon_seconds'])} s; "
                        f"{domain_labels[domain]}"
                    )
                    axes[row_index, column].fill_between(
                        x_values,
                        mean - 1.96 * error,
                        mean + 1.96 * error,
                        color=colors[schedule_index],
                        alpha=0.08 if domain else 0.14,
                    )
                    axes[row_index, column].plot(
                        x_values,
                        mean,
                        color=colors[schedule_index],
                        linestyle=linestyles[domain],
                        lw=1.7,
                        label=label,
                    )

    minimum = min(float(np.min(low)) for low, _ in plotted)
    maximum = max(float(np.max(high)) for _, high in plotted)
    margin = 0.08 * max(maximum - minimum, 1e-6)
    limits = (minimum - margin, maximum + margin)
    titles = (
        ("Own-impact build-up", "Cross-impact build-up"),
        ("Own-impact relaxation", "Cross-impact relaxation"),
    )
    for row in range(2):
        for column in range(2):
            axis = axes[row, column]
            axis.axhline(0.0, color="#777777", lw=0.7)
            axis.set_title(titles[row][column])
            axis.set_ylim(*limits)
            axis.grid(alpha=0.18, linewidth=0.5)
            if column == 0:
                axis.set_ylabel("Aggressor-signed log-mid response")
    axes[0, 0].set_xlabel("Scheduled cumulative meta-order volume")
    axes[0, 1].set_xlabel("Scheduled cumulative meta-order volume")
    axes[1, 0].set_xlabel("Lag after final child [s]")
    axes[1, 1].set_xlabel("Lag after final child [s]")
    axes[0, 0].legend(frameon=False, fontsize=7.2, loc="best")
    figure.suptitle(
        "Meta-order impact: equal signed volume, distinct execution horizons, explicit subordination"
    )
    figure.subplots_adjust(left=0.09, right=0.98, bottom=0.08, top=0.91, wspace=0.12, hspace=0.24)
    metadata = {
        "Creator": "correlation-emergence-v1.8.2",
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
    output = configuration["output_contract"]
    experiment = configuration["experiment"]
    input_start_hashes = snapshot_hashes(configuration["accepted_inputs"])
    accepted_errors = accepted_input_errors(configuration["accepted_inputs"])
    result = _run_experiment(configuration)
    _plot(result, configuration)

    all_filled = all(
        np.isclose(float(row["filled_quantity"]), float(row["quantity"]))
        for row in result["event_rows"]
    )
    schedule_totals = [float(row["total_quantity"]) for row in result["schedule_rows"]]
    schedule_horizons = [
        float(row["execution_horizon_seconds"]) for row in result["schedule_rows"]
    ]
    domains = {
        row["measurement_domain"]
        for row in result["trajectory_rows"] + result["relaxation_rows"]
    }
    matrix = configuration["impact_matrix"]
    input_end_errors = snapshot_errors(input_start_hashes)
    fast_final_own = float(result["own_trajectory"][0, -1])
    slow_final_own = float(result["own_trajectory"][1, -1])
    minimum_final_cross = float(np.min(result["cross_trajectory"][:, -1]))
    checks = [
        _check("S8M-01", "accepted v1.8.1 input hashes", not accepted_errors, "all accepted hashes exact", not accepted_errors),
        _check("S8M-02", "accepted parent", configuration["accepted_parent"], "equals v1.8.1", configuration["accepted_parent"] == "v1.8.1"),
        _check("S8M-03", "uniform operational dynamics", configuration["architecture"]["operational_dynamics"], "uniform_fixed_grid_only", configuration["architecture"]["operational_dynamics"] == "uniform_fixed_grid_only"),
        _check("S8M-04", "meta-order definition", configuration["architecture"]["meta_order"], "schedule of child market orders", configuration["architecture"]["meta_order"] == "declared_schedule_of_signed_child_market_order_events"),
        _check("S8M-05", "child application timing", configuration["architecture"]["event_application"], "each delta before its declared step", configuration["architecture"]["event_application"] == "each_child_density_delta_immediately_before_its_declared_operational_step"),
        _check("S8M-06", "paired-control construction", configuration["architecture"]["paired_control"], "common initial state and innovations", configuration["architecture"]["paired_control"] == "identical_initial_state_and_common_operational_innovations"),
        _check("S8M-07", "calendar observation", configuration["architecture"]["calendar_observation"], "same completed paths and clocks", configuration["architecture"]["calendar_observation"] == "same_completed_paths_same_book_specific_previous_refresh_clocks"),
        _check("S8M-08", "calendar interpolation", configuration["architecture"]["calendar_interpolation"], "forbidden", configuration["architecture"]["calendar_interpolation"] == "forbidden"),
        _check("S8M-09", "legacy nonuniform update", configuration["architecture"]["legacy_nonuniform_state_update"], "forbidden", configuration["architecture"]["legacy_nonuniform_state_update"] == "forbidden"),
        _check("S8M-10", "source-v1 change", configuration["architecture"]["source_v1_change"], "false", configuration["architecture"]["source_v1_change"] is False),
        _check("S8M-11", "declared path count", result["base_inputs"].shape[0], f"equals {experiment['paths']}", result["base_inputs"].shape[0] == int(experiment["paths"])),
        _check("S8M-12", "microscopic input correlation", result["input_correlation"], f"absolute <= {policy['maximum_input_correlation_absolute']}", abs(result["input_correlation"]) <= float(policy["maximum_input_correlation_absolute"])),
        _check("S8M-13", "two execution horizons", schedule_horizons, "two distinct positive horizons", len(schedule_horizons) == 2 and len(set(schedule_horizons)) == 2 and min(schedule_horizons) > 0.0),
        _check("S8M-14", "equal total meta-order quantity", schedule_totals, f"both equal {experiment['total_meta_order_quantity']}", all(np.isclose(value, float(experiment["total_meta_order_quantity"])) for value in schedule_totals)),
        _check("S8M-15", "all child market events fully filled", all_filled, "true", all_filled),
        _check("S8M-16", "child density-mass conservation", result["event_mass_error"], f"maximum <= {policy['maximum_child_density_mass_error']}", result["event_mass_error"] <= float(policy["maximum_child_density_mass_error"])),
        _check("S8M-17", "execution proxies lie on aggressor side", result["minimum_execution_side_product"], "strictly positive", result["minimum_execution_side_product"] > 0.0),
        _check("S8M-18", "pre-first-child shocked/control identity", result["pre_event_maximum"], f"maximum <= {policy['maximum_pre_first_event_absolute_paired_difference']}", result["pre_event_maximum"] <= float(policy["maximum_pre_first_event_absolute_paired_difference"])),
        _check("S8M-19", "unique reaction boundaries", result["maximum_candidates"], f"equals {policy['required_boundary_candidates']}", result["maximum_candidates"] == int(policy["required_boundary_candidates"])),
        _check("S8M-20", "interior reaction boundaries", result["minimum_edge"], f"minimum >= {policy['minimum_boundary_edge_distance']}", result["minimum_edge"] >= float(policy["minimum_boundary_edge_distance"])),
        _check("S8M-21", "first-child operational own impact", float(np.min(result["own_trajectory"][:, 0])), f">= {policy['minimum_first_child_operational_own_impact']}", float(np.min(result["own_trajectory"][:, 0])) >= float(policy["minimum_first_child_operational_own_impact"])),
        _check("S8M-22", "final-child operational own impact", float(np.min(result["own_trajectory"][:, -1])), f">= {policy['minimum_final_child_operational_own_impact']}", float(np.min(result["own_trajectory"][:, -1])) >= float(policy["minimum_final_child_operational_own_impact"])),
        _check("S8M-23", "final-child operational cross-impact", minimum_final_cross, f">= {policy['minimum_final_child_operational_cross_impact']}", minimum_final_cross >= float(policy["minimum_final_child_operational_cross_impact"])),
        _check("S8M-24", "operational own-impact build-up", result["minimum_own_increment"], "nonnegative across child states", result["minimum_own_increment"] >= -1e-12),
        _check("S8M-25", "execution-horizon effect", result["horizon_difference"], f"absolute final-own difference >= {policy['minimum_fast_slow_final_own_absolute_difference']}", result["horizon_difference"] >= float(policy["minimum_fast_slow_final_own_absolute_difference"])),
        _check("S8M-26", "book-exchange symmetry", result["book_difference"], f"maximum relative difference <= {policy['maximum_book_exchange_relative_difference']}", result["book_difference"] <= float(policy["maximum_book_exchange_relative_difference"])),
        _check("S8M-27", "buy/sell symmetry on domain own-impact scale", result["side_difference"], f"maximum <= {policy['maximum_buy_sell_domain_scaled_difference']}", result["side_difference"] <= float(policy["maximum_buy_sell_domain_scaled_difference"])),
        _check("S8M-28", "post-completion own-impact relaxation", result["own_relaxation_fractions"], f"every schedule >= {policy['minimum_post_completion_own_relaxation_fraction']}", bool(np.all(result["own_relaxation_fractions"] >= float(policy["minimum_post_completion_own_relaxation_fraction"])))),
        _check("S8M-29", "peak post-completion cross-impact catch-up", result["cross_catchup_fractions"], f"every schedule >= {policy['minimum_peak_post_completion_cross_catchup_fraction']}", bool(np.all(result["cross_catchup_fractions"] >= float(policy["minimum_peak_post_completion_cross_catchup_fraction"])))),
        _check("S8M-30", "long-lag own/cross convergence ratios", result["long_ratios"], f"all in [{policy['minimum_long_lag_own_cross_ratio']}, {policy['maximum_long_lag_own_cross_ratio']}]", bool(np.all((result["long_ratios"] >= float(policy["minimum_long_lag_own_cross_ratio"])) & (result["long_ratios"] <= float(policy["maximum_long_lag_own_cross_ratio"]))))),
        _check("S8M-31", "book-specific clock paths are distinct", result["distinct_clock_pairs"], "true for every path", result["distinct_clock_pairs"]),
        _check("S8M-32", "realised refresh rates", result["clock_relative_error"], "maximum relative error <= 0.35", result["clock_relative_error"] <= 0.35),
        _check("S8M-33", "calendar activity at 80 seconds after completion", result["calendar_active_eighty"], f">= {policy['minimum_calendar_active_fraction_at_80_seconds_after_completion']}", result["calendar_active_eighty"] >= float(policy["minimum_calendar_active_fraction_at_80_seconds_after_completion"])),
        _check("S8M-34", "calendar own impact at 80 seconds after completion", result["calendar_own_eighty"], f">= {policy['minimum_calendar_own_impact_at_80_seconds_after_completion']}", result["calendar_own_eighty"] >= float(policy["minimum_calendar_own_impact_at_80_seconds_after_completion"])),
        _check("S8M-35", "measurement domains", domains, "operational and calendar", domains == {"operational", "calendar"}),
        _check("S8M-36", "complete two-book impact matrix", {(row["event_book"], row["response_book"]) for row in matrix}, "four cells", {(row["event_book"], row["response_book"]) for row in matrix} == {(0, 0), (0, 1), (1, 0), (1, 1)}),
        _check("S8M-37", "trajectory curve rows", len(result["trajectory_rows"]), f"equals {output['trajectory_curve_rows']}", len(result["trajectory_rows"]) == int(output["trajectory_curve_rows"])),
        _check("S8M-38", "trajectory member rows", len(result["trajectory_member_rows"]), f"equals {output['trajectory_member_rows']}", len(result["trajectory_member_rows"]) == int(output["trajectory_member_rows"])),
        _check("S8M-39", "relaxation curve rows", len(result["relaxation_rows"]), f"equals {output['relaxation_curve_rows']}", len(result["relaxation_rows"]) == int(output["relaxation_curve_rows"])),
        _check("S8M-40", "relaxation member rows", len(result["relaxation_member_rows"]), f"equals {output['relaxation_member_rows']}", len(result["relaxation_member_rows"]) == int(output["relaxation_member_rows"])),
        _check("S8M-41", "child-event rows", len(result["event_rows"]), f"equals {output['event_rows']}", len(result["event_rows"]) == int(output["event_rows"])),
        _check("S8M-42", "schedule rows", len(result["schedule_rows"]), f"equals {output['schedule_rows']}", len(result["schedule_rows"]) == int(output["schedule_rows"])),
        _check("S8M-43", "path archive", PATH_ARCHIVE.is_file() and PATH_ARCHIVE.stat().st_size > 0, "nonempty NPZ", PATH_ARCHIVE.is_file() and PATH_ARCHIVE.stat().st_size > 0),
        _check("S8M-44", "Figure 10 pair", all(FIGURE_STEM.with_suffix(suffix).is_file() for suffix in (".pdf", ".png")), "PDF and PNG", all(FIGURE_STEM.with_suffix(suffix).is_file() for suffix in (".pdf", ".png"))),
        _check("S8M-45", "accepted inputs unchanged", not input_end_errors, "all start/end hashes exact", not input_end_errors),
        _check("S8M-46", "no new theoretical impact curve", output["new_theoretical_impact_curve"], "false", output["new_theoretical_impact_curve"] is False),
        _check("S8M-47", "participation-rate qualification", experiment["participation_rate_status"], "not identified without background volume", experiment["participation_rate_status"] == "not_identified_without_background_market_order_volume"),
        _check("S8M-48", "supplementary architecture inherited", configuration["supplementary_material_contract"]["inherit_v1_8_1_boundary_architecture_contrast"], "true", configuration["supplementary_material_contract"]["inherit_v1_8_1_boundary_architecture_contrast"] is True),
        _check("S8M-49", "dependence-stage boundary", configuration["stage_boundary"]["dependence_diagnostics_not_implemented"], "true", configuration["stage_boundary"]["dependence_diagnostics_not_implemented"] is True),
        _check("S8M-50", "next numeric gate", configuration["stage_boundary"]["next_stage_on_acceptance"], "v1.8.3 dependence diagnostics", configuration["stage_boundary"]["next_stage_on_acceptance"] == "v1.8.3_mid_price_and_trade_sign_dependence"),
    ]
    failed = sum(row["status"] == "Failed" for row in checks)
    summary = {
        "target_id": configuration["target_id"],
        "result_label": output["result_label_when_checks_pass"] if failed == 0 else "failed",
        "paths": experiment["paths"],
        "schedules": len(result["schedule_rows"]),
        "meta_order_scenarios": len(result["event_rows"]) // int(experiment["children_per_meta_order"]),
        "child_events": len(result["event_rows"]),
        "fast_final_operational_own_impact": fast_final_own,
        "slow_final_operational_own_impact": slow_final_own,
        "minimum_final_operational_cross_impact": minimum_final_cross,
        "fast_slow_final_own_absolute_difference": result["horizon_difference"],
        "minimum_post_completion_own_relaxation_fraction": float(np.min(result["own_relaxation_fractions"])),
        "minimum_peak_post_completion_cross_catchup_fraction": float(np.min(result["cross_catchup_fractions"])),
        "long_lag_own_cross_ratios": json.dumps(result["long_ratios"].tolist()),
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
        f"Meta-order impact route completed: {len(checks) - failed} checks verified, "
        f"{failed} failures; {len(result['event_rows'])} child-event rows."
    )
    print("Figure 10 generated on one common linear response scale.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
