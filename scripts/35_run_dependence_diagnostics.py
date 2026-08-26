"""Run v1.8.3 mid-price and three-convention trade-sign diagnostics."""

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
    operational_translation_event_tape_path,
    quote_midpoint_sign,
    tick_rule_signs,
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
from functions.path_diagnostics import increment_autocorrelation


VERSION = "1.8.3"
CONFIG_PATH = PROJECT_ROOT / "config" / "config-v1.8.3.json"
CHECK_PATH = PROJECT_ROOT / "diagnostics" / "dependence-diagnostic-checks-v1.8.csv"
PRICE_CURVE_PATH = PROJECT_ROOT / "outputs" / "dependence-mid-price-acf-v1.8.csv"
PRICE_MEMBER_PATH = PROJECT_ROOT / "outputs" / "dependence-mid-price-acf-members-v1.8.csv"
SIGN_CURVE_PATH = PROJECT_ROOT / "outputs" / "dependence-trade-sign-acf-v1.8.csv"
SIGN_MEMBER_PATH = PROJECT_ROOT / "outputs" / "dependence-trade-sign-acf-members-v1.8.csv"
CALENDAR_SIGN_CURVE_PATH = PROJECT_ROOT / "outputs" / "dependence-calendar-sign-flow-acf-v1.8.csv"
CALENDAR_SIGN_MEMBER_PATH = PROJECT_ROOT / "outputs" / "dependence-calendar-sign-flow-acf-members-v1.8.csv"
AGREEMENT_PATH = PROJECT_ROOT / "outputs" / "dependence-sign-agreement-v1.8.csv"
EVENT_PATH = PROJECT_ROOT / "outputs" / "dependence-event-tape-v1.8.csv"
CLOCK_PATH = PROJECT_ROOT / "outputs" / "dependence-clock-rates-v1.8.csv"
SUMMARY_PATH = PROJECT_ROOT / "outputs" / "dependence-summary-v1.8.csv"
PATH_ARCHIVE = PROJECT_ROOT / "outputs" / "dependence-paths-v1.8.npz"
FIGURE_STEM = PROJECT_ROOT / "figures" / "figure-11-mid-price-trade-sign-autocorrelations-v2"
CONVENTIONS = ("ground_truth_aggressor", "quote_midpoint", "legacy_tick_rule")


def _load_configuration() -> dict[str, object]:
    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if configuration.get("schema_version") != VERSION:
        raise ValueError("dependence configuration version mismatch")
    if configuration["architecture"]["calendar_interpolation"] != "forbidden":
        raise ValueError("v1.8.3 forbids calendar interpolation")
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


def _operational_inputs(configuration: dict[str, object]) -> np.ndarray:
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
    result = np.concatenate((primitive, -primitive), axis=0)
    if result.shape[0] != int(experiment["paths"]):
        raise ValueError("operational antithetic construction does not match path count")
    result.setflags(write=False)
    return result


def _declared_signs(configuration: dict[str, object]) -> np.ndarray:
    experiment = configuration["experiment"]
    primitive_paths = int(experiment["primitive_random_paths"])
    events = int(experiment["events_per_book_path"])
    repeat_probability = float(experiment["declared_sign_repeat_probability"])
    rng = np.random.default_rng(int(experiment["sign_seed"]))
    primitive = np.empty((primitive_paths, 2, events), dtype=int)
    for path in range(primitive_paths):
        for book in range(2):
            primitive[path, book, 0] = 1 if rng.random() >= 0.5 else -1
            repeat = rng.random(events - 1) < repeat_probability
            for index in range(1, events):
                primitive[path, book, index] = (
                    primitive[path, book, index - 1]
                    if repeat[index - 1]
                    else -primitive[path, book, index - 1]
                )
    result = np.concatenate((primitive, -primitive), axis=0)
    if result.shape[0] != int(experiment["paths"]):
        raise ValueError("sign antithetic construction does not match path count")
    result.setflags(write=False)
    return result


def _event_steps(configuration: dict[str, object]) -> np.ndarray:
    experiment = configuration["experiment"]
    count = int(experiment["events_per_book_path"])
    stride = int(experiment["same_book_event_stride_steps"])
    result = np.stack(
        [
            int(experiment[f"book_{book}_first_operational_step"])
            + stride * np.arange(count, dtype=int)
            for book in range(2)
        ]
    )
    if int(np.max(result)) > int(experiment["total_operational_steps"]):
        raise ValueError("declared events exceed operational support")
    result.setflags(write=False)
    return result


def _events_for_path(
    path_index: int,
    signs: np.ndarray,
    steps: np.ndarray,
    quantity: float,
) -> tuple[tuple[OrderEvent, ...], dict[str, tuple[int, int]]]:
    records: list[OrderEvent] = []
    positions: dict[str, tuple[int, int]] = {}
    for book in range(2):
        for event_index, operational_step in enumerate(steps[book]):
            event_id = f"v183-p{path_index:02d}-b{book + 1}-e{event_index + 1:03d}"
            positions[event_id] = (book, event_index)
            records.append(
                OrderEvent(
                    event_id=event_id,
                    event_type=EVENT_MARKET_ORDER,
                    book_index=book,
                    operational_step=int(operational_step),
                    side=int(signs[path_index, book, event_index]),
                    quantity=quantity,
                )
            )
    records.sort(key=lambda event: (event.operational_step, event.book_index, event.event_id))
    return tuple(records), positions


def _refresh_pairs(configuration: dict[str, object], horizon: float):
    experiment = configuration["experiment"]
    paths = int(experiment["paths"])
    count = int(experiment["clock_uniforms_per_book_path"])
    primitive = np.random.default_rng(int(experiment["clock_seed"])).random(
        (paths // 2, 2, count)
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
                    stream_id=f"v1.8.3-path-{path:02d}-book-{book + 1}",
                )
                for book in range(2)
            )
        )
    return tuple(result)


def _aggregate_book_members(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    path_values = np.mean(np.asarray(values, dtype=float), axis=1)
    mean = np.mean(path_values, axis=0)
    standard_error = np.std(path_values, axis=0, ddof=1) / np.sqrt(path_values.shape[0])
    return path_values, mean, standard_error


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


def _run_experiment(configuration: dict[str, object]) -> dict[str, object]:
    experiment = configuration["experiment"]
    paths = int(experiment["paths"])
    steps = int(experiment["total_operational_steps"])
    events_per_book = int(experiment["events_per_book_path"])
    quantity = float(experiment["event_quantity"])
    event_lag_maximum = int(experiment["event_lag_maximum"])
    price_lag_maximum = int(experiment["price_autocorrelation_maximum_lag"])
    diagnostic_start = int(experiment["price_diagnostic_start_operational_step"])
    diagnostic_stride = int(experiment["price_diagnostic_stride_steps"])
    step_seconds = float(configuration["model"]["operational_step_seconds"])
    sample_indices = np.arange(diagnostic_start, steps + 1, diagnostic_stride, dtype=int)
    if sample_indices.size < price_lag_maximum + 3:
        raise ValueError("price diagnostic window is too short")
    price_increment_count = sample_indices.size - 1
    operational_times_seconds = np.arange(steps + 1, dtype=float) * step_seconds
    grid, diffusion, sources, stationary, kernels, solver, couplings, innovation_policy = _model(configuration)
    base_inputs = _operational_inputs(configuration)
    declared_signs = _declared_signs(configuration)
    declared_steps = _event_steps(configuration)
    refresh_pairs = _refresh_pairs(configuration, float(operational_times_seconds[-1]))

    operational_prices = np.empty((paths, steps + 1, 2), dtype=float)
    calendar_prices = np.empty_like(operational_prices)
    calendar_indices = np.empty((paths, steps + 1, 2), dtype=np.int64)
    execution_prices = np.empty((paths, 2, events_per_book), dtype=float)
    pre_event_mids = np.empty_like(execution_prices)
    quote_signs = np.empty((paths, 2, events_per_book), dtype=int)
    tick_signs = np.empty_like(quote_signs)
    price_acf = np.empty((paths, 2, 2, price_lag_maximum + 1), dtype=float)
    event_sign_acf = np.empty((paths, 2, 3, event_lag_maximum + 1), dtype=float)
    calendar_sign_acf = np.empty((paths, 2, 3, price_lag_maximum + 1), dtype=float)
    event_rows: list[dict[str, object]] = []
    clock_rows: list[dict[str, object]] = []
    event_mass_errors: list[float] = []
    execution_side_products: list[float] = []
    minimum_edge = math.inf
    maximum_candidates = 0

    for path_index in range(paths):
        events, positions = _events_for_path(
            path_index, declared_signs, declared_steps, quantity
        )
        result = operational_translation_event_tape_path(
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
            events,
        )
        operational_prices[path_index] = result.prices
        minimum_edge = min(minimum_edge, float(np.min(result.boundary_edge_distances)))
        maximum_candidates = max(
            maximum_candidates, int(np.max(result.boundary_candidate_counts))
        )
        applications_by_position: dict[tuple[int, int], object] = {}
        for application in result.event_applications:
            book, event_index = positions[application.event.event_id]
            applications_by_position[(book, event_index)] = application
            execution_prices[path_index, book, event_index] = float(
                application.execution_log_price
            )
            pre_event_mids[path_index, book, event_index] = application.pre_event_mid_log_price
            quote_signs[path_index, book, event_index] = quote_midpoint_sign(application)
            applied_mass = float(
                (grid[1] - grid[0]) * np.sum(np.abs(application.density_delta))
            )
            event_mass_errors.append(abs(applied_mass - quantity))
            execution_side_products.append(
                application.event.side
                * (
                    float(application.execution_log_price)
                    - application.pre_event_mid_log_price
                )
            )
        for book in range(2):
            tick_signs[path_index, book] = tick_rule_signs(
                execution_prices[path_index, book]
            )
            for event_index in range(events_per_book):
                application = applications_by_position[(book, event_index)]
                event_rows.append(
                    {
                        "event_id": application.event.event_id,
                        "path_index": path_index,
                        "book_index": book,
                        "same_book_event_index": event_index,
                        "operational_step": application.event.operational_step,
                        "operational_time_seconds": application.event.operational_step * step_seconds,
                        "event_type": application.event.event_type,
                        "quantity": application.event.quantity,
                        "filled_quantity": application.filled_quantity,
                        "ground_truth_aggressor_sign": ground_truth_aggressor_sign(application),
                        "quote_midpoint_sign": quote_signs[path_index, book, event_index],
                        "legacy_tick_rule_sign": tick_signs[path_index, book, event_index],
                        "pre_event_mid_log_price": application.pre_event_mid_log_price,
                        "execution_log_price_proxy": application.execution_log_price,
                        "affected_grid_indices": json.dumps(application.affected_grid_indices),
                        "software_version": VERSION,
                    }
                )

        subordinated = subordinate_two_book_previous_refresh(
            operational_times_seconds,
            result.prices,
            refresh_pairs[path_index],
            operational_times_seconds,
        )
        calendar_prices[path_index] = subordinated.prices
        calendar_indices[path_index] = subordinated.operational_indices
        for book, clock in enumerate(refresh_pairs[path_index]):
            clock_rows.append(
                {
                    "path_index": path_index,
                    "book_index": book,
                    "stream_id": clock.stream_id,
                    "input_rate_per_second": clock.input_rate,
                    "measured_rate_per_second": clock.measured_rate,
                    "retained_waits": clock.waiting_intervals.size,
                    "supported_horizon_seconds": clock.supported_horizon,
                    "software_version": VERSION,
                }
            )

        for book in range(2):
            operational_increments = np.diff(result.prices[sample_indices, book])
            calendar_increments = np.diff(subordinated.prices[sample_indices, book])
            price_acf[path_index, book, 0] = increment_autocorrelation(
                operational_increments, price_lag_maximum
            )
            price_acf[path_index, book, 1] = increment_autocorrelation(
                calendar_increments, price_lag_maximum
            )

        convention_signs = np.stack(
            (declared_signs[path_index], quote_signs[path_index], tick_signs[path_index]),
            axis=1,
        )
        for book in range(2):
            for convention in range(3):
                event_sign_acf[path_index, book, convention] = increment_autocorrelation(
                    convention_signs[book, convention].astype(float),
                    event_lag_maximum,
                )

        for convention in range(3):
            event_increments = np.zeros((steps + 1, 2), dtype=float)
            for book in range(2):
                event_increments[declared_steps[book], book] = convention_signs[
                    book, convention
                ]
            cumulative = np.cumsum(event_increments, axis=0)
            sampled_cumulative = subordinate_two_book_previous_refresh(
                operational_times_seconds,
                cumulative,
                refresh_pairs[path_index],
                operational_times_seconds,
            ).prices
            binned_flow = np.diff(sampled_cumulative[sample_indices], axis=0)
            for book in range(2):
                calendar_sign_acf[path_index, book, convention] = increment_autocorrelation(
                    binned_flow[:, book], price_lag_maximum
                )
        print(f"  completed dependence path {path_index + 1}/{paths}", flush=True)

    price_path, price_mean, price_se = _aggregate_book_members(price_acf)
    sign_path, sign_mean, sign_se = _aggregate_book_members(event_sign_acf)
    calendar_sign_path, calendar_sign_mean, calendar_sign_se = _aggregate_book_members(
        calendar_sign_acf
    )
    diagnostic_interval_seconds = diagnostic_stride * step_seconds
    price_lags_seconds = np.arange(price_lag_maximum + 1) * diagnostic_interval_seconds
    event_lags = np.arange(event_lag_maximum + 1, dtype=int)

    price_curve_rows: list[dict[str, object]] = []
    price_member_rows: list[dict[str, object]] = []
    for domain, domain_name in enumerate(("operational", "calendar_previous_refresh")):
        for lag in range(price_lag_maximum + 1):
            price_curve_rows.append(
                {
                    "target_id": configuration["target_id"],
                    "measurement_domain": domain_name,
                    "lag_index": lag,
                    "lag_seconds": price_lags_seconds[lag],
                    "mean_increment_autocorrelation": price_mean[domain, lag],
                    "standard_error": price_se[domain, lag],
                    "normal_95_lower": price_mean[domain, lag] - 1.96 * price_se[domain, lag],
                    "normal_95_upper": price_mean[domain, lag] + 1.96 * price_se[domain, lag],
                    "effective_pairs_per_book_member": price_increment_count - lag,
                    "paths": paths,
                    "books_per_path": 2,
                    "level_autocorrelation_included": False,
                    "software_version": VERSION,
                }
            )
            for path_index in range(paths):
                for book in range(2):
                    price_member_rows.append(
                        {
                            "target_id": configuration["target_id"],
                            "path_index": path_index,
                            "book_index": book,
                            "measurement_domain": domain_name,
                            "lag_index": lag,
                            "lag_seconds": price_lags_seconds[lag],
                            "increment_autocorrelation": price_acf[path_index, book, domain, lag],
                            "effective_pairs": price_increment_count - lag,
                            "software_version": VERSION,
                        }
                    )

    sign_curve_rows: list[dict[str, object]] = []
    sign_member_rows: list[dict[str, object]] = []
    for convention, convention_name in enumerate(CONVENTIONS):
        for lag in range(event_lag_maximum + 1):
            sign_curve_rows.append(
                {
                    "target_id": configuration["target_id"],
                    "sign_convention": convention_name,
                    "event_lag": lag,
                    "mean_sign_autocorrelation": sign_mean[convention, lag],
                    "standard_error": sign_se[convention, lag],
                    "normal_95_lower": sign_mean[convention, lag] - 1.96 * sign_se[convention, lag],
                    "normal_95_upper": sign_mean[convention, lag] + 1.96 * sign_se[convention, lag],
                    "effective_pairs_per_book_member": events_per_book - lag,
                    "paths": paths,
                    "books_per_path": 2,
                    "software_version": VERSION,
                }
            )
            for path_index in range(paths):
                for book in range(2):
                    sign_member_rows.append(
                        {
                            "target_id": configuration["target_id"],
                            "path_index": path_index,
                            "book_index": book,
                            "sign_convention": convention_name,
                            "event_lag": lag,
                            "sign_autocorrelation": event_sign_acf[path_index, book, convention, lag],
                            "effective_pairs": events_per_book - lag,
                            "software_version": VERSION,
                        }
                    )

    calendar_sign_curve_rows: list[dict[str, object]] = []
    calendar_sign_member_rows: list[dict[str, object]] = []
    for convention, convention_name in enumerate(CONVENTIONS):
        for lag in range(price_lag_maximum + 1):
            calendar_sign_curve_rows.append(
                {
                    "target_id": configuration["target_id"],
                    "sign_convention": convention_name,
                    "calendar_lag_index": lag,
                    "calendar_lag_seconds": price_lags_seconds[lag],
                    "mean_signed_flow_autocorrelation": calendar_sign_mean[convention, lag],
                    "standard_error": calendar_sign_se[convention, lag],
                    "normal_95_lower": calendar_sign_mean[convention, lag] - 1.96 * calendar_sign_se[convention, lag],
                    "normal_95_upper": calendar_sign_mean[convention, lag] + 1.96 * calendar_sign_se[convention, lag],
                    "effective_pairs_per_book_member": price_increment_count - lag,
                    "bin_seconds": diagnostic_interval_seconds,
                    "paths": paths,
                    "books_per_path": 2,
                    "software_version": VERSION,
                }
            )
            for path_index in range(paths):
                for book in range(2):
                    calendar_sign_member_rows.append(
                        {
                            "target_id": configuration["target_id"],
                            "path_index": path_index,
                            "book_index": book,
                            "sign_convention": convention_name,
                            "calendar_lag_index": lag,
                            "calendar_lag_seconds": price_lags_seconds[lag],
                            "signed_flow_autocorrelation": calendar_sign_acf[path_index, book, convention, lag],
                            "effective_pairs": price_increment_count - lag,
                            "software_version": VERSION,
                        }
                    )

    sign_arrays = {
        "ground_truth_aggressor": declared_signs,
        "quote_midpoint": quote_signs,
        "legacy_tick_rule": tick_signs,
    }
    agreement_rows: list[dict[str, object]] = []
    for first, second in (
        ("ground_truth_aggressor", "quote_midpoint"),
        ("ground_truth_aggressor", "legacy_tick_rule"),
        ("quote_midpoint", "legacy_tick_rule"),
    ):
        left = sign_arrays[first].ravel()
        right = sign_arrays[second].ravel()
        agreement = float(np.mean(left == right))
        agreement_rows.append(
            {
                "first_convention": first,
                "second_convention": second,
                "agreement_fraction": agreement,
                "disagreement_fraction": 1.0 - agreement,
                "effective_events": left.size,
                "both_positive": int(np.sum((left == 1) & (right == 1))),
                "both_negative": int(np.sum((left == -1) & (right == -1))),
                "first_positive_second_nonpositive": int(np.sum((left == 1) & (right != 1))),
                "first_negative_second_nonnegative": int(np.sum((left == -1) & (right != -1))),
                "software_version": VERSION,
            }
        )

    write_csv(PRICE_CURVE_PATH, list(price_curve_rows[0]), price_curve_rows)
    write_csv(PRICE_MEMBER_PATH, list(price_member_rows[0]), price_member_rows)
    write_csv(SIGN_CURVE_PATH, list(sign_curve_rows[0]), sign_curve_rows)
    write_csv(SIGN_MEMBER_PATH, list(sign_member_rows[0]), sign_member_rows)
    write_csv(CALENDAR_SIGN_CURVE_PATH, list(calendar_sign_curve_rows[0]), calendar_sign_curve_rows)
    write_csv(CALENDAR_SIGN_MEMBER_PATH, list(calendar_sign_member_rows[0]), calendar_sign_member_rows)
    write_csv(AGREEMENT_PATH, list(agreement_rows[0]), agreement_rows)
    write_csv(EVENT_PATH, list(event_rows[0]), event_rows)
    write_csv(CLOCK_PATH, list(clock_rows[0]), clock_rows)
    np.savez_compressed(
        PATH_ARCHIVE,
        base_standard_normals=base_inputs,
        declared_event_steps=declared_steps,
        declared_ground_truth_signs=declared_signs,
        execution_log_price_proxies=execution_prices,
        pre_event_mid_log_prices=pre_event_mids,
        quote_midpoint_signs=quote_signs,
        legacy_tick_rule_signs=tick_signs,
        operational_times_seconds=operational_times_seconds,
        operational_prices=operational_prices,
        calendar_prices=calendar_prices,
        calendar_operational_indices=calendar_indices,
        diagnostic_sample_indices=sample_indices,
        mid_price_increment_autocorrelations=price_acf,
        event_sign_autocorrelations=event_sign_acf,
        calendar_sign_flow_autocorrelations=calendar_sign_acf,
    )
    measured_rates = np.asarray([row["measured_rate_per_second"] for row in clock_rows])
    input_rates = np.asarray([row["input_rate_per_second"] for row in clock_rows])
    operational_sampled_increments = np.diff(
        operational_prices[:, sample_indices, :], axis=1
    )
    calendar_sampled_increments = np.diff(calendar_prices[:, sample_indices, :], axis=1)
    return {
        "base_inputs": base_inputs,
        "declared_signs": declared_signs,
        "declared_steps": declared_steps,
        "quote_signs": quote_signs,
        "tick_signs": tick_signs,
        "operational_prices": operational_prices,
        "calendar_prices": calendar_prices,
        "calendar_indices": calendar_indices,
        "price_acf": price_acf,
        "price_path": price_path,
        "price_mean": price_mean,
        "price_se": price_se,
        "event_sign_acf": event_sign_acf,
        "sign_path": sign_path,
        "sign_mean": sign_mean,
        "sign_se": sign_se,
        "calendar_sign_acf": calendar_sign_acf,
        "calendar_sign_path": calendar_sign_path,
        "calendar_sign_mean": calendar_sign_mean,
        "calendar_sign_se": calendar_sign_se,
        "price_lags_seconds": price_lags_seconds,
        "event_lags": event_lags,
        "sample_indices": sample_indices,
        "agreement_rows": agreement_rows,
        "event_rows": event_rows,
        "clock_rows": clock_rows,
        "price_curve_rows": price_curve_rows,
        "price_member_rows": price_member_rows,
        "sign_curve_rows": sign_curve_rows,
        "sign_member_rows": sign_member_rows,
        "calendar_sign_curve_rows": calendar_sign_curve_rows,
        "calendar_sign_member_rows": calendar_sign_member_rows,
        "event_mass_error": max(event_mass_errors),
        "minimum_execution_side_product": min(execution_side_products),
        "minimum_edge": minimum_edge,
        "maximum_candidates": maximum_candidates,
        "clock_relative_error": float(np.max(np.abs(measured_rates - input_rates) / input_rates)),
        "input_correlation": float(np.corrcoef(base_inputs.reshape(-1, 2).T)[0, 1]),
        "cross_book_sign_correlation": float(
            np.corrcoef(declared_signs[:, 0].ravel(), declared_signs[:, 1].ravel())[0, 1]
        ),
        "minimum_price_increment_variance": float(
            min(
                np.min(np.var(operational_sampled_increments, axis=1, ddof=1)),
                np.min(np.var(calendar_sampled_increments, axis=1, ddof=1)),
            )
        ),
    }


def _plot(result: dict[str, object]) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(10.8, 8.2), sharey=True)
    colors = ("#2166ac", "#b35806", "#1b7837")
    all_bounds: list[np.ndarray] = []

    price_labels = ("Uniform operational", "Previous-refresh calendar")
    for domain in range(2):
        mean = result["price_mean"][domain]
        error = result["price_se"][domain]
        lower = mean - 1.96 * error
        upper = mean + 1.96 * error
        all_bounds.extend((lower, upper))
        axes[0, 0].fill_between(
            result["price_lags_seconds"], lower, upper, color=colors[domain], alpha=0.14
        )
        axes[0, 0].plot(
            result["price_lags_seconds"],
            mean,
            color=colors[domain],
            lw=1.7,
            label=price_labels[domain],
        )

    convention_labels = (
        "Ground-truth aggressor",
        "Quote/midpoint rule",
        "Legacy tick rule",
    )
    for convention in range(3):
        mean = result["sign_mean"][convention]
        error = result["sign_se"][convention]
        lower = mean - 1.96 * error
        upper = mean + 1.96 * error
        all_bounds.extend((lower, upper))
        axes[0, 1].fill_between(
            result["event_lags"], lower, upper, color=colors[convention], alpha=0.12
        )
        axes[0, 1].plot(
            result["event_lags"],
            mean,
            color=colors[convention],
            lw=1.7,
            label=convention_labels[convention],
        )

        calendar_mean = result["calendar_sign_mean"][convention]
        calendar_error = result["calendar_sign_se"][convention]
        calendar_lower = calendar_mean - 1.96 * calendar_error
        calendar_upper = calendar_mean + 1.96 * calendar_error
        all_bounds.extend((calendar_lower, calendar_upper))
        axes[1, 0].fill_between(
            result["price_lags_seconds"],
            calendar_lower,
            calendar_upper,
            color=colors[convention],
            alpha=0.12,
        )
        axes[1, 0].plot(
            result["price_lags_seconds"],
            calendar_mean,
            color=colors[convention],
            lw=1.7,
            label=convention_labels[convention],
        )

    agreement = np.asarray(
        [row["agreement_fraction"] for row in result["agreement_rows"]], dtype=float
    )
    disagreement = 1.0 - agreement
    positions = np.arange(3, dtype=float)
    axes[1, 1].bar(
        positions - 0.18, agreement, width=0.36, color="#4d9221", label="Agreement"
    )
    axes[1, 1].bar(
        positions + 0.18, disagreement, width=0.36, color="#c51b7d", label="Disagreement"
    )
    axes[1, 1].set_xticks(
        positions,
        ("Truth–quote", "Truth–tick", "Quote–tick"),
        rotation=12,
    )
    all_bounds.extend((agreement, disagreement))

    minimum = min(float(np.min(values)) for values in all_bounds)
    lower_limit = min(-0.08, minimum - 0.08 * max(1.0 - minimum, 0.1))
    for axis in axes.flat:
        axis.axhline(0.0, color="#777777", lw=0.7)
        axis.set_ylim(lower_limit, 1.06)
        axis.grid(alpha=0.18, linewidth=0.5)
        axis.set_ylabel("Correlation or fraction")
    axes[0, 0].set_title("Log-mid increment autocorrelation")
    axes[0, 0].set_xlabel("Lag [s]")
    axes[0, 0].legend(frameon=False, fontsize=7.5)
    axes[0, 1].set_title("Trade-sign autocorrelation in event time")
    axes[0, 1].set_xlabel("Same-book event lag")
    axes[0, 1].legend(frameon=False, fontsize=7.5)
    axes[1, 0].set_title("Subordinated signed-flow autocorrelation")
    axes[1, 0].set_xlabel("Calendar lag [s]")
    axes[1, 0].legend(frameon=False, fontsize=7.5)
    axes[1, 1].set_title("Sign-convention agreement")
    axes[1, 1].set_xlabel("Convention pair")
    axes[1, 1].legend(frameon=False, fontsize=7.5)
    figure.suptitle(
        "Mid-price and trade-sign dependence: event time, operational time, and explicit subordination"
    )
    figure.subplots_adjust(
        left=0.09, right=0.98, bottom=0.09, top=0.91, wspace=0.18, hspace=0.25
    )
    metadata = {
        "Creator": "correlation-emergence-v1.8.3",
        "CreationDate": None,
        "ModDate": None,
    }
    atomic_savefig(figure, FIGURE_STEM.with_suffix(".pdf"), metadata=metadata)
    atomic_savefig(figure, FIGURE_STEM.with_suffix(".png"), dpi=200)
    plt.close(figure)


def main() -> int:
    remove_orphaned_figure_staging_files()
    configuration = _load_configuration()
    experiment = configuration["experiment"]
    policy = configuration["acceptance_policy"]
    output = configuration["output_contract"]
    input_start_hashes = snapshot_hashes(configuration["accepted_inputs"])
    accepted_errors = accepted_input_errors(configuration["accepted_inputs"])
    result = _run_experiment(configuration)
    _plot(result)

    event_rows = result["event_rows"]
    all_filled = all(
        np.isclose(float(row["filled_quantity"]), float(row["quantity"]))
        for row in event_rows
    )
    quote_equals_truth = np.array_equal(result["quote_signs"], result["declared_signs"])
    tick_first_zero = bool(np.all(result["tick_signs"][:, :, 0] == 0))
    tick_agreement = float(
        next(
            row["agreement_fraction"]
            for row in result["agreement_rows"]
            if row["first_convention"] == "ground_truth_aggressor"
            and row["second_convention"] == "legacy_tick_rule"
        )
    )
    ground_lag_one = float(result["sign_mean"][0, 1])
    price_domain_rmse = float(
        np.sqrt(np.mean((result["price_mean"][0] - result["price_mean"][1]) ** 2))
    )
    maximum_acf = float(
        max(
            np.max(np.abs(result["price_acf"])),
            np.max(np.abs(result["event_sign_acf"])),
            np.max(np.abs(result["calendar_sign_acf"])),
        )
    )
    lag_zero_identity = bool(
        np.all(result["price_acf"][..., 0] == 1.0)
        and np.all(result["event_sign_acf"][..., 0] == 1.0)
        and np.all(result["calendar_sign_acf"][..., 0] == 1.0)
    )
    calendar_paths_distinct = bool(
        np.any(np.abs(result["calendar_prices"] - result["operational_prices"]) > 0.0)
    )
    expected_events = int(experiment["paths"]) * 2 * int(experiment["events_per_book_path"])
    input_end_errors = snapshot_errors(input_start_hashes)
    checks = [
        _check("S8D-01", "accepted v1.8.2 input hashes", accepted_errors, "none", not accepted_errors),
        _check("S8D-02", "accepted parent", configuration["accepted_parent"], "v1.8.2", configuration["accepted_parent"] == "v1.8.2"),
        _check("S8D-03", "uniform operational event tape", configuration["architecture"]["operational_dynamics"], "complete_uniform_fixed_grid_event_tape", configuration["architecture"]["operational_dynamics"] == "complete_uniform_fixed_grid_event_tape"),
        _check("S8D-04", "event application timing", configuration["architecture"]["event_application"], "density delta before declared operational step", configuration["architecture"]["event_application"].startswith("each_market_event_density_delta")),
        _check("S8D-05", "calendar observation layer", configuration["architecture"]["calendar_observation"], "previous refresh after complete path", configuration["architecture"]["calendar_observation"] == "book_specific_previous_refresh_after_complete_operational_path"),
        _check("S8D-06", "calendar interpolation", configuration["architecture"]["calendar_interpolation"], "forbidden", configuration["architecture"]["calendar_interpolation"] == "forbidden"),
        _check("S8D-07", "legacy nonuniform state update", configuration["architecture"]["legacy_nonuniform_state_update"], "forbidden", configuration["architecture"]["legacy_nonuniform_state_update"] == "forbidden"),
        _check("S8D-08", "model-parameter refit", configuration["architecture"]["model_parameter_refit"], "forbidden", configuration["architecture"]["model_parameter_refit"] == "forbidden"),
        _check("S8D-09", "source-v1 change", configuration["architecture"]["source_v1_change"], "false", configuration["architecture"]["source_v1_change"] is False),
        _check("S8D-10", "declared path count", result["base_inputs"].shape[0], f"equals {experiment['paths']}", result["base_inputs"].shape[0] == int(experiment["paths"])),
        _check("S8D-11", "operational input correlation", result["input_correlation"], f"absolute <= {policy['maximum_operational_input_correlation_absolute']}", abs(result["input_correlation"]) <= float(policy["maximum_operational_input_correlation_absolute"])),
        _check("S8D-12", "complete market-event tape", len(event_rows), f"equals {expected_events}", len(event_rows) == expected_events),
        _check("S8D-13", "all market events fully filled", all_filled, "true", all_filled),
        _check("S8D-14", "event density-mass conservation", result["event_mass_error"], f"maximum <= {policy['maximum_event_density_mass_error']}", result["event_mass_error"] <= float(policy["maximum_event_density_mass_error"])),
        _check("S8D-15", "execution proxies lie on aggressor side", result["minimum_execution_side_product"], "strictly positive", result["minimum_execution_side_product"] > 0.0),
        _check("S8D-16", "unique reaction boundaries", result["maximum_candidates"], f"equals {policy['required_boundary_candidates']}", result["maximum_candidates"] == int(policy["required_boundary_candidates"])),
        _check("S8D-17", "interior reaction boundaries", result["minimum_edge"], f"minimum >= {policy['minimum_boundary_edge_distance']}", result["minimum_edge"] >= float(policy["minimum_boundary_edge_distance"])),
        _check("S8D-18", "ground-truth sign balance", float(abs(np.mean(result["declared_signs"]))), f"absolute <= {policy['maximum_ground_truth_sign_mean_absolute']}", abs(np.mean(result["declared_signs"])) <= float(policy["maximum_ground_truth_sign_mean_absolute"])),
        _check("S8D-19", "cross-book ground-truth sign correlation", result["cross_book_sign_correlation"], f"absolute <= {policy['maximum_cross_book_ground_truth_sign_correlation_absolute']}", abs(result["cross_book_sign_correlation"]) <= float(policy["maximum_cross_book_ground_truth_sign_correlation_absolute"])),
        _check("S8D-20", "ground-truth lag-one sign persistence", ground_lag_one, f"in [{policy['minimum_ground_truth_event_lag_one_autocorrelation']}, {policy['maximum_ground_truth_event_lag_one_autocorrelation']}]", float(policy["minimum_ground_truth_event_lag_one_autocorrelation"]) <= ground_lag_one <= float(policy["maximum_ground_truth_event_lag_one_autocorrelation"])),
        _check("S8D-21", "quote/midpoint signs", quote_equals_truth, "exactly equal ground truth", quote_equals_truth),
        _check("S8D-22", "quote and ground-truth event ACF", float(np.max(np.abs(result["event_sign_acf"][:, :, 0] - result["event_sign_acf"][:, :, 1]))), "exactly zero", np.array_equal(result["event_sign_acf"][:, :, 0], result["event_sign_acf"][:, :, 1])),
        _check("S8D-23", "legacy tick first-event convention", tick_first_zero, "first event in every book/path is zero", tick_first_zero),
        _check("S8D-24", "tick-rule ground-truth agreement", tick_agreement, f"in [{policy['minimum_tick_rule_ground_truth_agreement']}, {policy['maximum_tick_rule_ground_truth_agreement']}]", float(policy["minimum_tick_rule_ground_truth_agreement"]) <= tick_agreement <= float(policy["maximum_tick_rule_ground_truth_agreement"])),
        _check("S8D-25", "tick rule remains distinct", 1.0 - tick_agreement, "strictly positive disagreement", (1.0 - tick_agreement) > 0.0),
        _check("S8D-26", "autocorrelation lag-zero identities", lag_zero_identity, "all exact one", lag_zero_identity),
        _check("S8D-27", "autocorrelation bounds", maximum_acf, f"maximum absolute <= {policy['maximum_absolute_autocorrelation']}", maximum_acf <= float(policy["maximum_absolute_autocorrelation"])),
        _check("S8D-28", "mid-price increment variation", result["minimum_price_increment_variance"], f"minimum variance >= {policy['minimum_price_increment_variance']}", result["minimum_price_increment_variance"] >= float(policy["minimum_price_increment_variance"])),
        _check("S8D-29", "operational/calendar mid-price ACF separation", price_domain_rmse, f"RMSE >= {policy['minimum_operational_calendar_mid_price_acf_rmse']}", price_domain_rmse >= float(policy["minimum_operational_calendar_mid_price_acf_rmse"])),
        _check("S8D-30", "calendar image differs from operational path", calendar_paths_distinct, "true", calendar_paths_distinct),
        _check("S8D-31", "realised refresh rates", result["clock_relative_error"], f"maximum relative error <= {policy['maximum_realised_clock_rate_relative_error']}", result["clock_relative_error"] <= float(policy["maximum_realised_clock_rate_relative_error"])),
        _check("S8D-32", "three sign conventions", CONVENTIONS, "exact registered three", tuple(experiment["trade_sign_conventions"]) == CONVENTIONS),
        _check("S8D-33", "passive limit-order role", configuration["architecture"]["limit_order_role"], "passive nontrade excluded from trade signs", configuration["architecture"]["limit_order_role"] == "passive_nontrade_and_excluded_from_trade_sign_series"),
        _check("S8D-34", "level autocorrelation exclusion", configuration["architecture"]["level_autocorrelation"], "excluded", configuration["architecture"]["level_autocorrelation"] == "excluded"),
        _check("S8D-35", "mid-price curve rows", len(result["price_curve_rows"]), f"equals {output['mid_price_curve_rows']}", len(result["price_curve_rows"]) == int(output["mid_price_curve_rows"])),
        _check("S8D-36", "mid-price member rows", len(result["price_member_rows"]), f"equals {output['mid_price_member_rows']}", len(result["price_member_rows"]) == int(output["mid_price_member_rows"])),
        _check("S8D-37", "event-sign curve rows", len(result["sign_curve_rows"]), f"equals {output['event_sign_curve_rows']}", len(result["sign_curve_rows"]) == int(output["event_sign_curve_rows"])),
        _check("S8D-38", "event-sign member rows", len(result["sign_member_rows"]), f"equals {output['event_sign_member_rows']}", len(result["sign_member_rows"]) == int(output["event_sign_member_rows"])),
        _check("S8D-39", "calendar sign-flow curve rows", len(result["calendar_sign_curve_rows"]), f"equals {output['calendar_sign_curve_rows']}", len(result["calendar_sign_curve_rows"]) == int(output["calendar_sign_curve_rows"])),
        _check("S8D-40", "calendar sign-flow member rows", len(result["calendar_sign_member_rows"]), f"equals {output['calendar_sign_member_rows']}", len(result["calendar_sign_member_rows"]) == int(output["calendar_sign_member_rows"])),
        _check("S8D-41", "agreement rows", len(result["agreement_rows"]), f"equals {output['agreement_rows']}", len(result["agreement_rows"]) == int(output["agreement_rows"])),
        _check("S8D-42", "clock rows", len(result["clock_rows"]), f"equals {output['clock_rows']}", len(result["clock_rows"]) == int(output["clock_rows"])),
        _check("S8D-43", "path archive", PATH_ARCHIVE.is_file() and PATH_ARCHIVE.stat().st_size > 0, "nonempty NPZ", PATH_ARCHIVE.is_file() and PATH_ARCHIVE.stat().st_size > 0),
        _check("S8D-44", "Figure 11 pair", all(FIGURE_STEM.with_suffix(suffix).is_file() for suffix in (".pdf", ".png")), "PDF and PNG", all(FIGURE_STEM.with_suffix(suffix).is_file() for suffix in (".pdf", ".png"))),
        _check("S8D-45", "accepted inputs unchanged", input_end_errors, "all start/end hashes exact", not input_end_errors),
        _check("S8D-46", "declared persistence qualification", configuration["scientific_qualification"]["declared_sign_persistence_is_input_not_result"], "true", configuration["scientific_qualification"]["declared_sign_persistence_is_input_not_result"] is True),
        _check("S8D-47", "no new theoretical curve", output["new_theoretical_curve"], "false", output["new_theoretical_curve"] is False),
        _check("S8D-48", "Stage 8 closure boundary", configuration["stage_boundary"]["v1.8.3_closes_stage_8_on_acceptance"], "true", configuration["stage_boundary"]["v1.8.3_closes_stage_8_on_acceptance"] is True),
        _check("S8D-49", "next numeric gate", configuration["stage_boundary"]["next_stage_on_acceptance"], "v1.9.0 final integration", configuration["stage_boundary"]["next_stage_on_acceptance"] == "v1.9.0_final_estimator_aware_combined_epps_integration"),
    ]
    failed = sum(row["status"] == "Failed" for row in checks)
    summary = {
        "target_id": configuration["target_id"],
        "result_label": output["result_label_when_checks_pass"] if failed == 0 else "failed",
        "paths": experiment["paths"],
        "events": len(event_rows),
        "ground_truth_event_lag_one_autocorrelation": ground_lag_one,
        "quote_midpoint_ground_truth_agreement": float(np.mean(result["quote_signs"] == result["declared_signs"])),
        "legacy_tick_ground_truth_agreement": tick_agreement,
        "operational_calendar_mid_price_acf_rmse": price_domain_rmse,
        "cross_book_ground_truth_sign_correlation": result["cross_book_sign_correlation"],
        "minimum_price_increment_variance": result["minimum_price_increment_variance"],
        "verified_checks": len(checks) - failed,
        "failed_checks": failed,
        "stage_8_status": "closed_on_acceptance" if failed == 0 else "open",
        "next_stage": output["next_stage"],
        "software_version": VERSION,
    }
    write_csv(SUMMARY_PATH, list(summary), [summary])
    write_csv(CHECK_PATH, list(checks[0]), checks)
    for row in checks:
        print(f"{row['check_id']}: {row['status']} - {row['check']}")
    print(
        f"Dependence route completed: {len(checks) - failed} checks verified, "
        f"{failed} failures; {len(event_rows)} market-event records."
    )
    print("Figure 11 generated with log-mid increment and trade-sign autocorrelations; level autocorrelation is excluded.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
